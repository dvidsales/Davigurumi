from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION davigurumi_guard_ownership() RETURNS trigger AS $$
DECLARE expected uuid; linked uuid;
BEGIN
 IF TG_TABLE_NAME IN ('materials_material','purchasing_supplier','purchasing_purchase','projects_project','sales_client','sales_quote') AND TG_OP='UPDATE' THEN
  IF NEW.owner_id IS DISTINCT FROM OLD.owner_id THEN RAISE EXCEPTION 'Ownership is immutable' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_TABLE_NAME='purchasing_purchase' THEN
  IF NEW.supplier_id IS NOT NULL THEN
  SELECT owner_id INTO linked FROM purchasing_supplier WHERE id=NEW.supplier_id;
  IF linked IS DISTINCT FROM NEW.owner_id THEN RAISE EXCEPTION 'Cross-owner supplier' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='purchasing_purchaseitem' THEN
  SELECT owner_id INTO expected FROM purchasing_purchase WHERE id=NEW.purchase_id;
  SELECT owner_id INTO linked FROM materials_material WHERE id=NEW.material_id;
  IF linked IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Cross-owner purchase material' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='materials_stockmovement' THEN
  IF NEW.layer_id IS NOT NULL THEN
  SELECT material_id INTO linked FROM materials_costlayer WHERE id=NEW.layer_id;
  IF linked IS DISTINCT FROM NEW.material_id THEN RAISE EXCEPTION 'Wrong movement layer' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='projects_project' THEN
  IF NEW.current_revision_id IS NOT NULL THEN
   SELECT project_id INTO linked FROM projects_projectrevision WHERE id=NEW.current_revision_id;
   IF linked IS DISTINCT FROM NEW.id THEN RAISE EXCEPTION 'Invalid current project revision' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='projects_projectmaterial' THEN
  SELECT p.owner_id INTO expected FROM projects_project p JOIN projects_projectrevision r ON r.project_id=p.id WHERE r.id=NEW.revision_id;
  SELECT owner_id INTO linked FROM materials_material WHERE id=NEW.material_id;
  IF linked IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Cross-owner project material' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='projects_materialalternative' THEN
  SELECT p.owner_id INTO expected FROM projects_project p JOIN projects_projectrevision r ON r.project_id=p.id JOIN projects_projectmaterial l ON l.revision_id=r.id WHERE l.id=NEW.line_id;
  SELECT owner_id INTO linked FROM materials_material WHERE id=NEW.material_id;
  IF linked IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Cross-owner alternative' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='sales_quote' THEN
  IF NEW.client_id IS NOT NULL THEN
  SELECT owner_id INTO linked FROM sales_client WHERE id=NEW.client_id;
  IF linked IS DISTINCT FROM NEW.owner_id THEN RAISE EXCEPTION 'Cross-owner client' USING ERRCODE='23514'; END IF;
  END IF;
  IF NEW.current_version_id IS NOT NULL THEN
   SELECT quote_id INTO linked FROM sales_quoteversion WHERE id=NEW.current_version_id;
   IF linked IS DISTINCT FROM NEW.id THEN RAISE EXCEPTION 'Invalid current quote version' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='sales_quoteitem' THEN
  SELECT q.owner_id INTO expected FROM sales_quote q JOIN sales_quoteversion v ON v.quote_id=q.id WHERE v.id=NEW.version_id;
  SELECT p.owner_id INTO linked FROM projects_project p JOIN projects_projectrevision r ON r.project_id=p.id WHERE r.id=NEW.project_revision_id;
  IF linked IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Cross-owner quote project' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION davigurumi_guard_quote_version() RETURNS trigger AS $$
BEGIN
 IF OLD.published_at IS NOT NULL THEN
  IF ROW(NEW.quote_id,NEW.number,NEW.terms,NEW.delivery_date,NEW.valid_days,NEW.expires_at,NEW.published_at,NEW.total,NEW.public_snapshot,NEW.internal_snapshot,NEW.content_hash,NEW.pdf)
     IS DISTINCT FROM ROW(OLD.quote_id,OLD.number,OLD.terms,OLD.delivery_date,OLD.valid_days,OLD.expires_at,OLD.published_at,OLD.total,OLD.public_snapshot,OLD.internal_snapshot,OLD.content_hash,OLD.pdf) THEN
   RAISE EXCEPTION 'Published commercial content is immutable' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.status='approved' AND (NEW.approved_hash IS DISTINCT FROM NEW.content_hash OR NEW.accepted_at IS NULL) THEN
  RAISE EXCEPTION 'Approval requires exact published hash and timestamp' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION davigurumi_guard_quote_item() RETURNS trigger AS $$
DECLARE published timestamp with time zone; version_id uuid;
BEGIN
 IF TG_OP='DELETE' THEN version_id=OLD.version_id; ELSE version_id=NEW.version_id; END IF;
 SELECT published_at INTO published FROM sales_quoteversion WHERE id=version_id;
 IF published IS NOT NULL THEN RAISE EXCEPTION 'Published quote items are immutable' USING ERRCODE='23514'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$ LANGUAGE plpgsql;
"""

TABLES = [
    "materials_material",
    "materials_stockmovement",
    "purchasing_supplier",
    "purchasing_purchase",
    "purchasing_purchaseitem",
    "projects_project",
    "projects_projectmaterial",
    "projects_materialalternative",
    "sales_client",
    "sales_quote",
    "sales_quoteitem",
]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SQL)
    for table in TABLES:
        schema_editor.execute(
            f"CREATE TRIGGER ownership_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_ownership()"
        )
    schema_editor.execute(
        "CREATE TRIGGER quote_immutable BEFORE UPDATE ON sales_quoteversion FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_quote_version()"
    )
    schema_editor.execute(
        "CREATE TRIGGER quote_item_immutable BEFORE INSERT OR UPDATE OR DELETE ON sales_quoteitem FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_quote_item()"
    )


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS ownership_guard ON {table}")
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS quote_immutable ON sales_quoteversion"
    )
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS quote_item_immutable ON sales_quoteitem"
    )
    schema_editor.execute(
        "DROP FUNCTION IF EXISTS davigurumi_guard_ownership(), davigurumi_guard_quote_version(), davigurumi_guard_quote_item()"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0001_initial"),
        ("materials", "0006_alter_stockmovement_conversion_snapshot_and_more"),
        ("purchasing", "0001_initial"),
        ("projects", "0001_initial"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
