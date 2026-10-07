from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION davigurumi_guard_images() RETURNS trigger AS $$
DECLARE v uuid; a uuid; expected uuid; linked uuid; published timestamp with time zone;
BEGIN
 IF TG_TABLE_NAME='sales_fileasset' THEN
  IF ROW(NEW.owner_id,NEW.file,NEW.sha256,NEW.size,NEW.width,NEW.height) IS DISTINCT FROM ROW(OLD.owner_id,OLD.file,OLD.sha256,OLD.size,OLD.width,OLD.height) THEN
   RAISE EXCEPTION 'File objects are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='DELETE' THEN v=OLD.version_id; a=OLD.asset_id; ELSE v=NEW.version_id; a=NEW.asset_id; END IF;
 SELECT q.owner_id,cv.published_at INTO expected,published FROM sales_quote q JOIN sales_quoteversion cv ON cv.quote_id=q.id WHERE cv.id=v;
 SELECT owner_id INTO linked FROM sales_fileasset WHERE id=a;
 IF expected IS DISTINCT FROM linked THEN RAISE EXCEPTION 'Cross-owner quote image' USING ERRCODE='23514'; END IF;
 IF published IS NOT NULL THEN RAISE EXCEPTION 'Published image selections are immutable' USING ERRCODE='23514'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER image_owner_and_immutability BEFORE INSERT OR UPDATE OR DELETE ON sales_quoteimage FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_images();
CREATE TRIGGER file_immutability BEFORE UPDATE ON sales_fileasset FOR EACH ROW EXECUTE FUNCTION davigurumi_guard_images();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS image_owner_and_immutability ON sales_quoteimage; DROP TRIGGER IF EXISTS file_immutability ON sales_fileasset; DROP FUNCTION IF EXISTS davigurumi_guard_images();"
        )


class Migration(migrations.Migration):
    dependencies = [("sales", "0006_fileasset_quoteimage")]
    operations = [migrations.RunPython(install, uninstall)]
