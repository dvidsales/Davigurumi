from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION davigurumi_guard_operational_links() RETURNS trigger AS $$
DECLARE expected uuid; linked uuid; quote uuid; linked_quote uuid; published timestamp with time zone; allocated numeric; refunded numeric;
BEGIN
 IF TG_TABLE_NAME='production_order' THEN
  SELECT q.owner_id,q.id INTO expected,quote FROM sales_quote q JOIN sales_quoteversion v ON v.quote_id=q.id WHERE v.id=NEW.approved_version_id;
  SELECT q.owner_id,q.id INTO linked,linked_quote FROM sales_quote q JOIN sales_quoteversion v ON v.quote_id=q.id WHERE v.id=NEW.current_version_id;
  IF expected IS DISTINCT FROM NEW.owner_id OR linked IS DISTINCT FROM NEW.owner_id OR quote IS DISTINCT FROM linked_quote THEN RAISE EXCEPTION 'Invalid order owner/version' USING ERRCODE='23514'; END IF;
  IF TG_OP='UPDATE' THEN
   IF NEW.owner_id IS DISTINCT FROM OLD.owner_id OR NEW.approved_version_id IS DISTINCT FROM OLD.approved_version_id THEN RAISE EXCEPTION 'Order origin is immutable' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='production_orderitem' THEN
  SELECT owner_id INTO expected FROM production_order WHERE id=NEW.order_id;
  SELECT q.owner_id INTO linked FROM sales_quote q JOIN sales_quoteversion v ON v.quote_id=q.id JOIN sales_quoteitem i ON i.version_id=v.id WHERE i.id=NEW.source_item_id;
  IF expected IS DISTINCT FROM linked THEN RAISE EXCEPTION 'Cross-owner order item' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='production_consumption' THEN
  SELECT o.owner_id INTO expected FROM production_order o JOIN production_orderitem i ON i.order_id=o.id WHERE i.id=NEW.item_id;
  SELECT m.owner_id INTO linked FROM materials_material m JOIN materials_stockmovement s ON s.material_id=m.id WHERE s.id=NEW.movement_id;
  IF expected IS DISTINCT FROM linked THEN RAISE EXCEPTION 'Cross-owner consumption' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='production_productionsession' THEN
  SELECT o.owner_id INTO expected FROM production_order o JOIN production_orderitem i ON i.order_id=o.id WHERE i.id=NEW.item_id;
  IF expected IS DISTINCT FROM NEW.owner_id THEN RAISE EXCEPTION 'Cross-owner production session' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='finance_paymentallocation' THEN
  SELECT owner_id,amount INTO expected,allocated FROM finance_payment WHERE id=NEW.payment_id;
  SELECT q.owner_id,q.id INTO linked,quote FROM sales_quote q JOIN sales_quoteversion v ON v.quote_id=q.id WHERE v.id=NEW.version_id;
  IF expected IS DISTINCT FROM linked OR allocated IS DISTINCT FROM NEW.amount THEN RAISE EXCEPTION 'Invalid allocation owner/amount' USING ERRCODE='23514'; END IF;
  IF NEW.order_id IS NOT NULL THEN
   SELECT o.owner_id,v.quote_id INTO linked,linked_quote FROM production_order o JOIN sales_quoteversion v ON v.id=o.approved_version_id WHERE o.id=NEW.order_id;
   IF expected IS DISTINCT FROM linked OR quote IS DISTINCT FROM linked_quote THEN RAISE EXCEPTION 'Cross-owner allocation order' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='finance_refund' THEN
  IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Refunds are immutable' USING ERRCODE='23514'; END IF;
  SELECT amount INTO allocated FROM finance_paymentallocation WHERE id=NEW.allocation_id FOR UPDATE;
  SELECT coalesce(sum(amount),0) INTO refunded FROM finance_refund WHERE allocation_id=NEW.allocation_id;
  IF refunded+NEW.amount>allocated THEN RAISE EXCEPTION 'Refund exceeds net receipt' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='materials_stockmovement' THEN
  IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Physical ledger is append-only' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='materials_costlayer' THEN
  IF TG_OP='UPDATE' THEN
   IF ROW(NEW.material_id,NEW.original_quantity,NEW.unit_cost,NEW.lot) IS DISTINCT FROM ROW(OLD.material_id,OLD.original_quantity,OLD.unit_cost,OLD.lot) THEN RAISE EXCEPTION 'Cost-layer origin is immutable' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='materials_stockreservation' THEN
  IF TG_OP='UPDATE' THEN
   IF ROW(NEW.layer_id,NEW.quantity,NEW.reference) IS DISTINCT FROM ROW(OLD.layer_id,OLD.quantity,OLD.reference) THEN RAISE EXCEPTION 'Reservation origin is immutable' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
"""
TABLES = [
    "production_order",
    "production_orderitem",
    "production_consumption",
    "production_productionsession",
    "finance_paymentallocation",
    "finance_refund",
    "materials_stockmovement",
    "materials_costlayer",
    "materials_stockreservation",
]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SQL)
    for table in TABLES:
        schema_editor.execute(
            f"CREATE TRIGGER operational_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_operational_links()"
        )


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS operational_guard ON {table}")
    schema_editor.execute(
        "DROP FUNCTION IF EXISTS davigurumi_guard_operational_links()"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_initial"),
        ("sales", "0004_quoteitem_line_key_quoteversion_amends_version"),
        ("production", "0001_initial"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
