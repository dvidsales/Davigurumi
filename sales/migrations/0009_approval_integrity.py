from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION davigurumi_guard_approval_origin() RETURNS trigger AS $$
DECLARE parent uuid;
BEGIN
 IF NEW.amends_version_id IS NOT NULL THEN
  SELECT quote_id INTO parent FROM sales_quoteversion WHERE id=NEW.amends_version_id;
  IF parent IS DISTINCT FROM NEW.quote_id OR NEW.amends_version_id=NEW.id THEN
   RAISE EXCEPTION 'Invalid amendment origin' USING ERRCODE='23514';
  END IF;
 END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.published_at IS NOT NULL AND ROW(NEW.amends_version_id,NEW.approval_origin) IS DISTINCT FROM ROW(OLD.amends_version_id,OLD.approval_origin) THEN
   RAISE EXCEPTION 'Published origin is immutable' USING ERRCODE='23514';
  END IF;
  IF OLD.accepted_at IS NOT NULL AND ROW(NEW.accepted_at,NEW.approved_hash) IS DISTINCT FROM ROW(OLD.accepted_at,OLD.approved_hash) THEN
   RAISE EXCEPTION 'Recorded approval is immutable' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER approval_origin_guard BEFORE INSERT OR UPDATE ON sales_quoteversion FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_approval_origin();
CREATE OR REPLACE FUNCTION davigurumi_guard_payment_origin() RETURNS trigger AS $$
BEGIN
 IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Confirmed payment origin is immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER payment_origin_guard BEFORE UPDATE ON finance_payment FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_payment_origin();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS approval_origin_guard ON sales_quoteversion; DROP TRIGGER IF EXISTS payment_origin_guard ON finance_payment; DROP FUNCTION IF EXISTS davigurumi_guard_approval_origin(),davigurumi_guard_payment_origin()"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0008_quoteversion_approval_origin"),
        ("finance", "0003_integrity_guards"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
