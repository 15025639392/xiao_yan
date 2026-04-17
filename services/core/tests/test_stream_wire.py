from app.llm.openai_responses_stream_wire import iter_openai_responses_stream_events
from app.llm.stream_wire import iter_chat_completions_stream_events, iter_responses_stream_events


def test_iter_responses_stream_events_completed_payload_can_correct_bad_delta_accumulation():
    events = list(
        iter_responses_stream_events(
            [
                'event: response.created',
                'data: {"response":{"id":"resp_1"}}',
                "",
                'event: response.output_text.delta',
                'data: {"delta":"你好你好"}',
                "",
                "event: response.output_text.delta",
                "data: {not-json}",
                "",
                'event: response.completed',
                'data: {"response":{"id":"resp_1","output":[{"type":"message","content":[{"type":"output_text","text":"你好"}]}]}}',
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "resp_1"},
        {"type": "text_delta", "delta": "你好你好"},
        {
            "type": "response_completed",
            "response_id": "resp_1",
            "output_text": "你好",
        },
    ]


def test_iter_chat_completions_stream_events_completes_on_length_finish_reason_after_invalid_frame():
    events = list(
        iter_chat_completions_stream_events(
            [
                'data: {"id":"chatcmpl_1","choices":[{"delta":{"role":"assistant"}}]}',
                "",
                "data: {not-json}",
                "",
                'data: {"id":"chatcmpl_1","choices":[{"delta":{"content":"先回答一半"}}]}',
                "",
                'data: {"id":"chatcmpl_1","choices":[{"finish_reason":"length"}]}',
                "",
                "data: [DONE]",
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "chatcmpl_1"},
        {"type": "text_delta", "delta": "先回答一半"},
        {
            "type": "response_completed",
            "response_id": "chatcmpl_1",
            "output_text": "先回答一半",
        },
    ]


def test_iter_chat_completions_stream_events_preserves_text_when_tool_call_deltas_follow():
    events = list(
        iter_chat_completions_stream_events(
            [
                'data: {"id":"chatcmpl_tool_1","choices":[{"delta":{"role":"assistant"}}]}',
                "",
                'data: {"id":"chatcmpl_tool_1","choices":[{"delta":{"content":"我先查一下天气。"}}]}',
                "",
                (
                    'data: {"id":"chatcmpl_tool_1","choices":[{"delta":{"tool_calls":'
                    '[{"index":0,"id":"call_1","type":"function","function":{"name":"get_weather","arguments":"{\\"city\\":\\"Bei"}}]}}]}'
                ),
                "",
                (
                    'data: {"id":"chatcmpl_tool_1","choices":[{"delta":{"tool_calls":'
                    '[{"index":0,"function":{"arguments":"jing\\"}"}}]}}]}'
                ),
                "",
                'data: {"id":"chatcmpl_tool_1","choices":[{"finish_reason":"tool_calls"}]}',
                "",
                "data: [DONE]",
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "chatcmpl_tool_1"},
        {"type": "text_delta", "delta": "我先查一下天气。"},
        {
            "type": "response_completed",
            "response_id": "chatcmpl_tool_1",
            "output_text": "我先查一下天气。",
        },
    ]


def test_iter_chat_completions_stream_events_handles_tool_call_only_stream_without_text():
    events = list(
        iter_chat_completions_stream_events(
            [
                'data: {"id":"chatcmpl_tool_2","choices":[{"delta":{"role":"assistant"}}]}',
                "",
                (
                    'data: {"id":"chatcmpl_tool_2","choices":[{"delta":{"tool_calls":'
                    '[{"index":0,"id":"call_2","type":"function","function":{"name":"search_docs","arguments":"{\\"query\\":\\"hel"}}]}}]}'
                ),
                "",
                (
                    'data: {"id":"chatcmpl_tool_2","choices":[{"delta":{"tool_calls":'
                    '[{"index":0,"function":{"arguments":"lo\\"}"}}]}}]}'
                ),
                "",
                'data: {"id":"chatcmpl_tool_2","choices":[{"finish_reason":"tool_calls"}]}',
                "",
                "data: [DONE]",
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "chatcmpl_tool_2"},
        {
            "type": "response_completed",
            "response_id": "chatcmpl_tool_2",
            "output_text": "",
        },
    ]


def test_iter_responses_stream_events_completed_payload_concatenates_multiple_message_items():
    events = list(
        iter_responses_stream_events(
            [
                'event: response.created',
                'data: {"response":{"id":"resp_multi_1"}}',
                "",
                'event: response.output_text.delta',
                'data: {"delta":"错误前缀"}',
                "",
                (
                    'event: response.completed'
                ),
                (
                    'data: {"response":{"id":"resp_multi_1","output":['
                    '{"type":"message","content":[{"type":"output_text","text":"第一段。"}]},'
                    '{"type":"reasoning","summary":[{"type":"summary_text","text":"忽略"}]},'
                    '{"type":"message","content":[{"type":"output_text","text":"第二段。"}]}'
                    ']}}'
                ),
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "resp_multi_1"},
        {"type": "text_delta", "delta": "错误前缀"},
        {
            "type": "response_completed",
            "response_id": "resp_multi_1",
            "output_text": "第一段。第二段。",
        },
    ]


def test_iter_openai_responses_stream_events_ignores_tool_and_content_part_deltas():
    events = list(
        iter_openai_responses_stream_events(
            [
                'event: response.created',
                'data: {"response":{"id":"resp_openai_1"}}',
                "",
                'event: response.output_item.added',
                'data: {"item":{"type":"function_call","id":"fc_1"}}',
                "",
                'event: response.content_part.added',
                'data: {"part":{"type":"output_text","text":"ignored carrier"}}',
                "",
                'event: response.output_text.delta',
                'data: {"delta":"保留这段文本。"}',
                "",
                'event: response.function_call_arguments.delta',
                'data: {"delta":"{\\"query\\":\\"hello\\"}"}',
                "",
                'event: response.completed',
                'data: {"response":{"id":"resp_openai_1"}}',
                "",
            ]
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "resp_openai_1"},
        {"type": "text_delta", "delta": "保留这段文本。"},
        {
            "type": "response_completed",
            "response_id": "resp_openai_1",
            "output_text": "保留这段文本。",
        },
    ]
