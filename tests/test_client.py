from types import SimpleNamespace

from bridge_builder.client import _extract


def test_extract_json_text():
    result = SimpleNamespace(content=[SimpleNamespace(text='{"ok": true, "girders": 0}')])
    assert _extract(result) == {"ok": True, "girders": 0}


def test_extract_structured_result_string():
    result = SimpleNamespace(content=None, structured_content={"result": '{"ok": false, "error": "timeout"}'})
    assert _extract(result)["error"] == "timeout"


def test_render_prompt_shows_embedded_resources_and_text():
    from bridge_builder.client import _render_prompt

    result = SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="user",
                content=SimpleNamespace(
                    type="resource", resource=SimpleNamespace(uri="bridge://clients/fetnis", text="# FETNIS")
                ),
            ),
            SimpleNamespace(role="user", content=SimpleNamespace(type="text", text="Build it.")),
        ]
    )
    assert _render_prompt(result) == "[user] resource bridge://clients/fetnis\n# FETNIS\n\n[user] Build it."
