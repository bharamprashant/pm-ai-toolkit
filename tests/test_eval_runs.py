"""Repeat-run and prompt-version plumbing of the eval, with fake models (no network, no key)."""
from modules.m01_status_agent import agent
from modules.m01_status_agent.eval.run_eval import evaluate, summarize


class _Echo:
    """Answers like the baseline but records which system prompt it was given."""
    name = "fake"

    def __init__(self):
        self.systems = []

    def complete_json(self, system, user):
        self.systems.append(system)
        return agent._baseline_fn(system, user)


def test_prompts_differ_and_v2_is_a_superset_rule():
    assert agent.PROMPTS["v1"] == agent.SYSTEM
    assert agent.PROMPTS["v2"] != agent.SYSTEM
    assert "rate the workstream RED" in agent.PROMPTS["v2"]
    assert "rate the workstream RED" not in agent.SYSTEM


def test_evaluate_passes_the_chosen_prompt_to_the_model():
    llm = _Echo()
    evaluate(llm, agent.PROMPTS["v2"])
    assert llm.systems and set(llm.systems) == {agent.PROMPTS["v2"]}
    llm = _Echo()
    evaluate(llm)
    assert set(llm.systems) == {agent.SYSTEM}


def test_summarize_reports_range_and_miss_frequency():
    base = evaluate(agent.baseline())
    better = dict(base, accuracy=1.0, misses=[])
    s = summarize([base, better, base])
    assert s["runs"] == 3
    assert s["accuracy_min"] == base["accuracy"] and s["accuracy_max"] == 1.0
    assert s["case_misses"][0]["missed_in_runs"] == 2
