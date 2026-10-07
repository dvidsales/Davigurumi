from django.db import migrations

SQL = """
CREATE FUNCTION davigurumi_guard_actual_expense() RETURNS trigger AS $$
DECLARE original_order uuid; original_amount numeric; original_reverses uuid;
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Expense history is append-only' USING ERRCODE='23514'; END IF;
 IF NEW.reverses_id IS NOT NULL THEN
  SELECT order_id,amount,reverses_id INTO original_order,original_amount,original_reverses FROM production_actualexpense WHERE id=NEW.reverses_id FOR UPDATE;
  IF original_order IS DISTINCT FROM NEW.order_id OR original_amount IS DISTINCT FROM NEW.amount OR original_reverses IS NOT NULL THEN
   RAISE EXCEPTION 'Invalid expense reversal' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER expense_integrity BEFORE INSERT OR UPDATE OR DELETE ON production_actualexpense FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_actual_expense();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS expense_integrity ON production_actualexpense; DROP FUNCTION IF EXISTS davigurumi_guard_actual_expense();"
        )


class Migration(migrations.Migration):
    dependencies = [("production", "0002_actualexpense")]
    operations = [migrations.RunPython(install, uninstall)]
