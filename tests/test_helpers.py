from utils.helpers import (
    extract_first_url,
    extract_json_array,
    extract_key_terms,
    strip_code_block,
)


def test_extract_json_array_plain():
    assert extract_json_array('[{"a": 1}]') == [{"a": 1}]


def test_extract_json_array_with_code_fence():
    text = '```json\n[{"a": 1}, {"a": 2}]\n```'
    assert extract_json_array(text) == [{"a": 1}, {"a": 2}]


def test_extract_json_array_with_surrounding_prose():
    text = 'Here you go:\n[{"a": 1}]\nHope that helps!'
    assert extract_json_array(text) == [{"a": 1}]


def test_extract_json_array_no_json_returns_empty():
    assert extract_json_array("no json here") == []


def test_extract_json_array_none_returns_empty():
    assert extract_json_array(None) == []


def test_extract_key_terms_drops_filler_words():
    assert extract_key_terms("how to learn Claude Code for development") == "learn claude code"


def test_extract_key_terms_falls_back_to_topic_when_empty():
    assert extract_key_terms("to a in") == "to a in"


def test_extract_first_url_found():
    assert extract_first_url("Here is the link: https://example.com/audio.mp3 enjoy") == (
        "https://example.com/audio.mp3"
    )


def test_extract_first_url_none_when_missing():
    assert extract_first_url("no links here") is None


def test_extract_first_url_none_for_empty_input():
    assert extract_first_url(None) is None


def test_strip_code_block_removes_fences():
    assert strip_code_block("```text\nHello world\n```") == "Hello world"


def test_strip_code_block_leaves_plain_text_untouched():
    assert strip_code_block("Hello world") == "Hello world"
