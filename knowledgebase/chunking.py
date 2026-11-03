def _fit(word, count, limit):
    """Split a single oversized 'word' so that every piece fits the limit."""
    if len(word) < 2 or count(word) <= limit:
        return [word]
    mid = len(word) // 2
    return _fit(word[:mid], count, limit) + _fit(word[mid:], count, limit)


def chunk_text(text, count_tokens, *, max_tokens, min_tokens, overlap_tokens):
    """Greedy chunks of at most max_tokens, with overlap. Only the final chunk can be below min_tokens.
    Token counts are summed per word, so use the embedding model's own tokenizer for count_tokens."""
    if not 0 <= overlap_tokens < min_tokens < max_tokens:
        raise ValueError("Require 0 <= overlap < min < max")
    limit = max_tokens - min_tokens             # a single piece this small can never break the 'min' guarantee
    words = [piece for word in text.split() for piece in _fit(word, count_tokens, limit)]
    costs = [count_tokens(w) for w in words]
    chunks, start, n = [], 0, len(words)
    while start < n:
        end, total = start, 0
        while end < n and total + costs[end] <= max_tokens:
            total += costs[end]
            end += 1
        if end == start:
            end = start + 1
        chunks.append(" ".join(words[start:end]))
        if end >= n:
            break
        back, kept = end, 0
        while back > start + 1 and kept + costs[back - 1] <= overlap_tokens:
            back -= 1
            kept += costs[back]
        start = back
    return chunks