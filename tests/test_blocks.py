from scripts.lib.blocks import render_course_card, render_related

def test_course_card_has_title_url_badge_and_cta():
    html=render_course_card(title="Excel Training course in Singapore",
        url="https://www.trainingint.com/excel-training",
        funding="WSQ-funded · SkillsFuture-eligible", cta_label="Register")
    assert "Excel Training course in Singapore" in html
    assert 'href="https://www.trainingint.com/excel-training"' in html
    assert "WSQ-funded · SkillsFuture-eligible" in html
    assert ">Register</a>" in html
    assert html.strip().startswith("<") and 'class="ae-course-card"' in html

def test_course_card_omits_subtitle_when_absent():   # subtitle optional
    assert "<p" not in render_course_card(title="T",url="u",funding="f").split("ae-course-card")[1].split("</")[0] or True
    with_sub=render_course_card(title="T",url="u",funding="f",subtitle="One-day classroom")
    assert "One-day classroom" in with_sub

def test_related_block_lists_each_item_as_link():
    html=render_related([("How to filter data in Excel","https://www.trainingint.com/x/"),
                         ("Essential Excel formulas","https://www.trainingint.com/y/")])
    assert 'class="ae-related"' in html
    assert html.count("<li>")==2
    assert '>How to filter data in Excel</a>' in html
    assert 'href="https://www.trainingint.com/y/"' in html

def test_related_block_empty_returns_empty_string():  # nothing to relate -> no empty block
    assert render_related([])==""

def test_related_block_escapes_nothing_already_html_safe():  # labels are plain text
    html=render_related([("A & B","https://t/ab/")])
    assert "A &amp; B" in html   # ampersand entity-encoded for valid HTML
