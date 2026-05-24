from scripts.sync_status import reconcile_status

def test_future_post_stays_scheduled_and_gets_clean_url():
    entry={"status":"scheduled","wp_post_id":17447,"url":None,"scheduled_date":"2026-05-25"}
    wp={"status":"future","link":"https://www.trainingint.com/essential-excel-formulas.html"}
    out=reconcile_status(entry,wp)
    assert out["status"]=="scheduled"
    assert out["url"]=="https://www.trainingint.com/essential-excel-formulas.html"
    assert out["wp_post_id"]==17447 and out["scheduled_date"]=="2026-05-25"  # preserved

def test_published_post_flips_to_published():   # the vlookup drift case
    entry={"status":"scheduled","wp_post_id":17434,"scheduled_date":"2026-05-22"}
    wp={"status":"publish",
        "link":"https://www.trainingint.com/how-to-use-vlookup-and-xlookup-in-excel.html"}
    out=reconcile_status(entry,wp)
    assert out["status"]=="published"
    assert out["url"].endswith("how-to-use-vlookup-and-xlookup-in-excel.html")

def test_draft_maps_to_draft():
    out=reconcile_status({"status":"scheduled","wp_post_id":1},{"status":"draft","link":"u"})
    assert out["status"]=="draft"

def test_does_not_mutate_input():   # ADVERSARIAL: in-place edit corrupts the loaded yaml
    entry={"status":"scheduled","wp_post_id":1,"url":None}
    reconcile_status(entry,{"status":"publish","link":"u"})
    assert entry["status"]=="scheduled" and entry["url"] is None
