# takopi-engine-kimi

[Kimi CLI](https://github.com/MoonshotAI/kimi-cli) engine plugin for [Takopi](https://github.com/banteg/takopi).

## Installation

### With pip

```bash
pip install takopi-engine-kimi
```

### With uv (in a project)

```bash
# Add to your project's dependencies
uv add takopi takopi-engine-kimi

# Or from git (before it's published)
uv add takopi git+https://github.com/z80dev/takopi-engine-kimi

# Or from local path during development
uv add takopi /path/to/takopi-engine-kimi
```

### With uv (as a tool)

```bash
# Install takopi with the kimi plugin
uv tool install takopi --with takopi-engine-kimi

# Or from git
uv tool install takopi --with git+https://github.com/z80dev/takopi-engine-kimi

# Or upgrade an existing installation
uv tool upgrade takopi --with takopi-engine-kimi
```

### With uv tool run (temporary)

```bash
# Run takopi with kimi support without installing
uv tool run --with takopi-engine-kimi --from takopi takopi
```

## Usage

Once installed, the `kimi` engine is automatically available. The plugin defaults to:

- **Model**: `kimi-for-coding` (Kimi's coding-optimized model)

Minimal configuration in `takopi.toml`:

```toml
[engines.kimi]
# Uses "kimi-for-coding" by default
```

Enable auto-approval (yolo mode):

```toml
[engines.kimi]
yolo = true  # Auto-approve all actions
```

Full configuration options:

```toml
[engines.kimi]
model = "kimi-for-coding"  # Or "kimi-k2", etc.
allowed_tools = ["Bash", "Read", "Edit", "Write"]
yolo = true  # Auto-approve all actions
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
| `model` | string | `kimi-for-coding` | Kimi model to use |
| `allowed_tools` | list[string] | `["Bash", "Read", "Edit", "Write"]` | Tools to allow |
| `yolo` | boolean | `false` | Auto-approve all actions (Kimi's `--yolo` flag) |
| `use_api_billing` | boolean | `false` | Use API billing mode |

## Requirements

- Python >= 3.14
- Takopi >= 0.22.0
- [Kimi CLI](https://github.com/MoonshotAI/kimi-cli) installed

## License

MIT
