# takopi-kimi-runner

[Kimi CLI](https://github.com/MoonshotAI/kimi-cli) runner plugin for [Takopi](https://github.com/banteg/takopi).

## Installation

### With pip

```bash
pip install takopi-kimi-runner
```

### With uv (in a project)

```bash
# Add to your project's dependencies
uv add takopi takopi-kimi-runner

# Or from git (before it's published)
uv add takopi git+https://github.com/yourusername/takopi-kimi-runner

# Or from local path during development
uv add takopi /path/to/takopi-kimi-runner
```

### With uv (as a tool)

```bash
# Install takopi with the kimi plugin
uv tool install takopi --with takopi-kimi-runner

# Or from git
uv tool install takopi --with git+https://github.com/yourusername/takopi-kimi-runner

# Or upgrade an existing installation
uv tool upgrade takopi --with takopi-kimi-runner
```

### With uv tool run (temporary)

```bash
# Run takopi with kimi support without installing
uv tool run --with takopi-kimi-runner --from takopi takopi
```

## Usage

Once installed, the `kimi` engine is automatically available. Add to your `takopi.toml`:

```toml
[engines.kimi]
model = "kimi-k2"
allowed_tools = ["Bash", "Read", "Edit", "Write"]
# dangerously_skip_permissions = false
```

## Verification

Verify the plugin is installed:

```bash
# Check available engines
uv run python -c "from takopi.engines import list_backend_ids; print(list_backend_ids())"
# ['claude', 'codex', 'kimi', 'opencode', 'pi']
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
