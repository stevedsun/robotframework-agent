# robotframework-agent

LLM agent keywords for [Robot Framework](https://robotframework.org), in the
spirit of [tester-army/e2e](https://github.com/tester-army/e2e): state a goal
or an expectation in natural language, and a model drives or judges the
application.

```robot
*** Settings ***
Library    Browser
Library    RobotAgent

*** Test Cases ***
Login With The Agent
    New Page    https://www.saucedemo.com/
    AGENT ACT      log in as standard_user with password secret_sauce
    AGENT ASSERT   the page shows the product list, titled Products
```

## Keywords

| Keyword | What it does |
| --- | --- |
| `AGENT ACT  instruction  [max_steps]  [timeout]` | The model loops over click / type / scroll tools until the goal is reached or certainly cannot be; failure fails the test with the model's reason. Returns the model's summary. |
| `AGENT ASSERT  instruction  [screenshot=True]` | One judgment call over the current screen (plus a viewport screenshot): `holds` passes, `fails` / `inconclusive` fail the test with the explanation. |

## How it works

- **Engine**: the library borrows the running
  [robotframework-browser](https://github.com/MarketSquare/robotframework-browser)
  instance. `Evaluate JavaScript` tags every interactive element with a stable
  id (`data-rfa-id="n42"`) and returns an indented text tree; actions run
  through the Browser library's own `Click` / `Fill Text` / `Press Keys`, so
  the agent shares the browser your suite already opened.
- **Act loop**: an LLM tool-calling loop (LiteLLM). Every action result
  carries the fresh screen; the step ends only through the `done` verdict
  tool. `max_steps` / `timeout` bound the loop, and a spent budget triggers a
  wind-down in which only the verdict tool is offered.
- **Assert**: a single judgment call answering
  `{explanation, verdict: holds | fails | inconclusive}` — the third verdict
  keeps the model honest when the evidence is thin.
- **Prompt safety**: observation and instruction are fenced as DATA, not
  instructions; the model is told never to invent node ids.

## Setup

```bash
pip install -e .
rfbrowser init        # Playwright browsers for the Browser library
export AGENT_MODEL=gpt-4o           # any LiteLLM model name
export OPENAI_API_KEY=...           # or ANTHROPIC_API_KEY, etc.
robot -d results tests/demo.robot
```

## Library arguments

| Argument | Default | Meaning |
| --- | --- | --- |
| `model` | `${AGENT_MODEL}` env var | LiteLLM model name, e.g. `gpt-4o`, `anthropic/claude-sonnet-4-5`, `deepseek/deepseek-chat` |
| `browser_library` | `Browser` | Name the Browser library was imported as |
| `max_steps` | `10` | Default action budget per `AGENT ACT` |
| `timeout` | `2 minutes` | Default wall-clock budget per `AGENT ACT` |
| `max_observation_chars` | `8000` | Character budget of the screen text sent to the model |

## Not (yet) ported from e2e

Action recording and replay caching, mobile engines, secrets redaction,
custom project tools, multi-agent config. The tree is re-sent whole after
every action instead of diffed.
