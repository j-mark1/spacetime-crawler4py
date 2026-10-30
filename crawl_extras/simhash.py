'''
Simhash fingerprints for spotting near-duplicate pages (only sha256 comes from a library)
'''

from hashlib import sha256

BITS = 64         # Should be big enough to avoid unwatned collisions
MAX_DISTANCE = 3  # pages whose fingerprints differ in this many bits or fewer are near duplicates

def fingerprint(tokens):
    weights = {}
    for token in tokens:
        weights[token] = weights.get(token, 0) + 1

    votes = [0] * BITS
    for token, weight in weights.items():
        word_hash = _hash64(token)
        for bit in range(BITS):
            if (word_hash >> bit) & 1:
                votes[bit] += weight
            else:
                votes[bit] -= weight

    result = 0
    # for each bit, if the corresponding element in the vec is > 0
    # The flip the bit to 1, otherwise leave as 0
    for bit in range(BITS):
        if votes[bit] > 0:
            result |= 1 << bit
    return result

# number of bits that differ, counts xor 1s(different bits)
def distance(a, b):
    return (a ^ b).bit_count()

def is_near_duplicate(a, b):
    return distance(a, b) <= MAX_DISTANCE

# first 8 bytes of the word's sha256 as an int
def _hash64(token):
    digest = sha256(token.encode("utf-8")).digest()
    result = 0
    for byte in digest[:BITS // 8]:
        result = (result << 8) | byte
    return result
