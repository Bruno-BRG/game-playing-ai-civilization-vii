# NVIDIA model benchmark

The gameplay loop needs reliable tool calls more than long prose. On July 31, 2026, three hosted
NVIDIA Build models were tested against the same constrained scenarios: choose required research,
wait while the local turn is inactive, and advance when no blocker remains.

| Model | Mean latency | Correct decisions | Role |
| --- | ---: | ---: | --- |
| `nvidia/nemotron-3-nano-30b-a3b` | 0.985 s | 3/3 | Default gameplay loop |
| `nvidia/nvidia-nemotron-nano-9b-v2` | 1.158 s | 3/3 | Older fallback |
| `meta/llama-3.1-8b-instruct` | 4.179 s | 3/3 | Not selected |
| `nvidia/nemotron-3-ultra-550b-a55b` | about 6 s | Smoke test passed | Strategic profile |

These numbers include hosted network and queue time, so they will vary. Nano 30B-A3B won because it
was both fastest and correct in every scenario. Its active MoE size is only 3B parameters, while its
training explicitly covers instruction following and tool calling. A named `choose_action` tool
choice was also materially faster and more reliable than the generic `required` mode in this test.

The default profile therefore uses:

```text
model: nvidia/nemotron-3-nano-30b-a3b
thinking: false
temperature: 0.6
top_p: 0.95
max_tokens: 512
tool_choice: choose_action (named)
```

The optional `strategic` profile keeps Nemotron 3 Ultra with thinking enabled for future decisions
that justify extra latency, such as long-horizon research, expansion, diplomacy, or victory plans.

References:

- [Nemotron 3 Nano on NVIDIA Build](https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b)
- [Nemotron Nano 9B v2 on NVIDIA Build](https://build.nvidia.com/nvidia/nvidia-nemotron-nano-9b-v2)
- [Llama 3.1 8B on NVIDIA Build](https://build.nvidia.com/meta/llama-3_1-8b-instruct)
- [NVIDIA tool-calling support](https://docs.nvidia.com/nim/large-language-models/latest/function-calling.html)
