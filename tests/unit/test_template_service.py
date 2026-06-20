from app.services.template_service import render_template


def test_render_template_basic():
    result = render_template(
        "Hello {{name}}, your order {{order_id}} has shipped.",
        {"name": "Asha", "order_id": "123"},
    )
    assert result == "Hello Asha, your order 123 has shipped."


def test_render_template_missing_variable_left_untouched():
    result = render_template("Hi {{name}}", {})
    assert result == "Hi {{name}}"


def test_render_template_none_input_returns_none():
    assert render_template(None, {"x": 1}) is None


def test_render_template_tolerates_whitespace_in_braces():
    result = render_template("Hi {{ name }}", {"name": "Sam"})
    assert result == "Hi Sam"


def test_render_template_numeric_value_stringified():
    result = render_template("You have {{count}} new messages", {"count": 5})
    assert result == "You have 5 new messages"
