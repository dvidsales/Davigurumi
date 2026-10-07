from django.db import migrations

SQL = """
CREATE FUNCTION davigurumi_guard_compensation() RETURNS trigger AS $$
DECLARE source_material uuid; source_quantity numeric; source_cost numeric; source_reverses uuid; already numeric; expected uuid; linked uuid;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Physical ledger is append-only' USING ERRCODE='23514'; END IF;
 SELECT owner_id INTO expected FROM materials_material WHERE id=NEW.material_id;
 IF NEW.operation_id IS NOT NULL THEN
  SELECT owner_id INTO linked FROM materials_stockoperation WHERE id=NEW.operation_id;
  IF linked IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Cross-owner stock operation' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.reverses_id IS NOT NULL THEN
  SELECT material_id,quantity,unit_cost,reverses_id INTO source_material,source_quantity,source_cost,source_reverses FROM materials_stockmovement WHERE id=NEW.reverses_id FOR UPDATE;
  SELECT coalesce(sum(abs(quantity)),0) INTO already FROM materials_stockmovement WHERE reverses_id=NEW.reverses_id;
  IF source_material IS DISTINCT FROM NEW.material_id OR source_cost IS DISTINCT FROM NEW.unit_cost OR source_reverses IS NOT NULL OR source_quantity*NEW.quantity>=0 OR already+abs(NEW.quantity)>abs(source_quantity) THEN
   RAISE EXCEPTION 'Invalid stock compensation' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER compensation_integrity BEFORE INSERT OR DELETE ON materials_stockmovement FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_compensation();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS compensation_integrity ON materials_stockmovement; DROP FUNCTION IF EXISTS davigurumi_guard_compensation();"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0009_alter_stockmovement_reverses"),
        ("finance", "0003_integrity_guards"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
