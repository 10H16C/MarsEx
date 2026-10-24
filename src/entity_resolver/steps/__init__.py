"""The resolution steps, in pipeline order.

1. normalize       - casefold and collapse whitespace
2. exact lookup    - a unique stored alias resolves immediately (in resolver.py)
3. cache           - reuse a validated result for the same input and pipeline version
4. candidates      - nominate products by exact, substring, and subsequence name matching
5. llm             - pick one candidate or none; resolver.py applies the score threshold
"""
