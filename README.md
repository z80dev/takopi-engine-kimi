# takopi-kimi-runner

[Kimi CLI](https://github.com/MoonshotAI/kimi-cli) runner plugin for [Takopi](https://github.com/banteg/takopi).

## Installation

```bash
pip install takopi-kimi-runner
```

This plugin registers itself via entry points, so once installed, Takopi will automatically discover the `kimi` engine.

## Usage

Add to your `takopi.toml`:

```toml
[engines.kimi]
model = "kimi-k2"
allowed_tools = ["Bash", "Read", "Edit", "Write"]
# dangerously_skip_permissions = false
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | - | Kimi model to use (e.g., `kimi-k2`) |
| `allowed_tools` | list[string] | `["Bash", "Read", "Edit", "Write"]` | Tools to allow |
| `dangerously_skip_permissions` | boolean | false | Skip permission prompts |
| `use_api_billing` | boolean | false | Use API billing mode |

## Requirements

- Python >= 3.14
- Takopi >= 0.22.0
- [Kimi CLI](https://github.com/MoonshotAI/kimi-cli) installed

## License

MIT
