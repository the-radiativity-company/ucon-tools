<table>
  <tr>
    <td width="200">
      <img src="https://gist.githubusercontent.com/withtwoemms/8386e69ff949733a99dbc41bdab0dc1e/raw/42c00e74a37ff091f415ffec7292b8eceac18cbb/ucon-tools-logo.png" align="left" width="200" />
    </td>
    <td>

# ucon-tools

[![tests](https://github.com/withtwoemms/ucon-tools/workflows/tests/badge.svg)](https://github.com/withtwoemms/ucon-tools/actions?query=workflow%3Atests)
[![codecov](https://codecov.io/gh/withtwoemms/ucon-tools/graph/badge.svg?token=HDKWKAF7PX)](https://codecov.io/gh/withtwoemms/ucon-tools)
[![publish](https://github.com/withtwoemms/ucon-tools/workflows/publish/badge.svg)](https://github.com/withtwoemms/ucon-tools/actions?query=workflow%3Apublish)

   </td>
  </tr>
</table>

> An **MCP server** that gives AI agents dimensionally-verified unit conversion and computation — powered by [ucon](https://github.com/withtwoemms/ucon).

**[Documentation](https://docs.ucon.dev)** · [MCP Server Guide](https://docs.ucon.dev/guides/mcp-server/) · [Tool Reference](https://docs.ucon.dev/reference/mcp-tools/)

---

## What is ucon-tools?

`ucon-tools` exposes the [ucon](https://github.com/withtwoemms/ucon) dimensional analysis engine as an [MCP](https://modelcontextprotocol.io/) server. AI agents (Claude, Cursor, and other MCP clients) can convert units, perform multi-step factor-label calculations, and define custom units at runtime — with dimensional consistency validated at every step.

```
Agent: "Convert 5 mcg/kg/min for an 80 kg patient to mL/h. Drug is 400 mg in 250 mL."

  decompose → constraint solver places quantities, auto-bridges mcg→mg and min→h
  compute   → 5 × 80 kg × (60 min/h) × (1 mg/1000 mcg) × (250 mL/400 mg) = 15 mL/h
  validate  → result dimension matches expected unit ✓
```

---

## Installation

```bash
pip install ucon-tools[mcp]
```

Requires Python 3.10+.

---

## Quick Start

### Claude Desktop / Claude Code

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "ucon": {
      "command": "uvx",
      "args": ["--from", "ucon-tools[mcp]", "ucon-mcp"]
    }
  }
}
```

### Standalone

```bash
ucon-mcp                    # stdio transport (default)
ucon-mcp --transport sse    # SSE transport for remote clients
```

---

## MCP Tools

### Core

| Tool | Description |
|------|-------------|
| `convert` | Convert a value between compatible units |
| `compute` | Multi-step factor-label calculation with dimensional tracking |
| `decompose` | Build a factor chain from natural-language or structured input |
| `check_dimensions` | Check if two units share the same dimension |

### Discovery

| Tool | Description |
|------|-------------|
| `list_units` | List available units, optionally filtered by dimension |
| `list_scales` | List SI decimal and binary prefixes |
| `list_dimensions` | List available physical dimensions |
| `list_constants` | List physical constants (CODATA 2022) |
| `list_formulas` | List registered domain formulas |

### Runtime Extension

| Tool | Description |
|------|-------------|
| `define_unit` | Register a custom unit for the session |
| `define_conversion` | Add a conversion edge (linear or affine) |
| `define_constant` | Define a custom physical constant |
| `call_formula` | Call a registered dimensionally-typed formula |
| `reset_session` | Clear all session-defined units, conversions, and constants |

### Kind-of-Quantity (KOQ)

| Tool | Description |
|------|-------------|
| `define_quantity_kind` | Register a quantity kind for semantic disambiguation |
| `declare_computation` | Declare expected quantity kind before computing |
| `validate_result` | Validate that a result matches the declared kind |
| `list_quantity_kinds` | List registered quantity kinds |
| `extend_basis` | Create an extended dimensional basis |
| `list_extended_bases` | List session-defined extended bases |

---

## Relationship to ucon

`ucon` is the core library — it defines units, dimensions, scales, and the conversion graph.

`ucon-tools` is the interface layer — it wraps `ucon` in an MCP server so agents can use it. It also adds agent-specific capabilities that don't belong in the core library: the `decompose` constraint solver, session state management, fuzzy error suggestions, and KOQ disambiguation.

```
┌─────────────────────────────────────────┐
│              MCP Client                 │
│     (Claude, Cursor, etc.)              │
└────────────────┬────────────────────────┘
                 │ MCP protocol
┌────────────────▼────────────────────────┐
│            ucon-tools                   │
│  MCP server, decompose, KOQ, sessions   │
└────────────────┬────────────────────────┘
                 │ Python imports
┌────────────────▼────────────────────────┐
│               ucon                      │
│  Units, dimensions, ConversionGraph     │
└─────────────────────────────────────────┘
```

---

## Development

```bash
make venv                               # Create virtual environment
source .ucon-tools-3.12/bin/activate    # Activate
make test                               # Run tests
make test-all                           # Run across all supported Python versions
```

### Running the MCP server locally

```bash
make mcp-server                         # Foreground (stdio)
make mcp-server-bg                      # Background
make mcp-server-stop                    # Stop background server
```

---

## License

AGPL-3.0. See [LICENSE](./LICENSE).
