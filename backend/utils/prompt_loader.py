from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

def load_prompt(name: str) -> str:
    """
    Load a prompt from the prompts/ directory.
    Strips comment lines (starting with #) and leading/trailing whitespace.
    
    Args:
        name: filename without .txt extension (e.g. 'eligibility_system')
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    
    lines = path.read_text(encoding="utf-8").splitlines()
    # Strip comment lines and blank lines at top
    content_lines = []
    started = False
    for line in lines:
        if line.startswith("#") and not started:
            continue
        started = True
        content_lines.append(line)
    
    return "\n".join(content_lines).strip()
