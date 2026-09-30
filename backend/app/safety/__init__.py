"""Stage 6A: safety. Everything here is rule-based and offline (patterns and checksums, no AI).

  scanner.py    finds private data and attack indicators in the sources
  shield.py     prompt-injection shield: instructions aimed at the AI, hidden characters, hidden text
  masking.py    swaps hidden values for placeholders before the AI, and the "leak check" afterwards
  tlp.py        the sharing label (TLP): suggestion and which outputs each label allows
  decisions.py  saves every safety decision (who, when, what) in the safety_decisions table
"""
