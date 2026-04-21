from typing import List, Dict, Set


class LCProblem:
    def __init__(self, lc_id, slug, title, difficulty, tags):
        self.lc_id = lc_id
        self.slug = slug
        self.title = title
        self.difficulty = difficulty
        self.tags = tags


def lc_bank() -> Dict[str, List[LCProblem]]:
    return {
        "Arrays & Hashing": [
            LCProblem(1, "two-sum", "Two Sum", "Easy", ["Array", "Hash Table"]),
            LCProblem(36, "valid-sudoku", "Valid Sudoku", "Medium", ["Array", "Hash Table"]),
            LCProblem(49, "group-anagrams", "Group Anagrams", "Medium", ["Array", "Hash Table", "Sorting"]),
            LCProblem(128, "longest-consecutive-sequence", "Longest Consecutive Sequence", "Medium", ["Array", "Hash Table"]),
        ],
        "Two Pointers": [
            LCProblem(125, "valid-palindrome", "Valid Palindrome", "Easy", ["Two Pointers"]),
            LCProblem(15, "3sum", "3Sum", "Medium", ["Array", "Sorting"]),
            LCProblem(42, "trapping-rain-water", "Trapping Rain Water", "Hard", ["DP", "Stack"]),
        ],
        "Sliding Window": [
            LCProblem(3, "longest-substring-without-repeating-characters", "Longest Substring Without Repeating Characters", "Medium", ["String", "Sliding Window"]),
            LCProblem(76, "minimum-window-substring", "Minimum Window Substring", "Hard", ["Sliding Window"]),
        ],
        "Trees": [
            LCProblem(226, "invert-binary-tree", "Invert Binary Tree", "Easy", ["Tree"]),
            LCProblem(104, "maximum-depth-of-binary-tree", "Max Depth of Binary Tree", "Easy", ["Tree"]),
        ],
        "Graphs": [
            LCProblem(200, "number-of-islands", "Number of Islands", "Medium", ["DFS", "BFS"]),
            LCProblem(207, "course-schedule", "Course Schedule", "Medium", ["Graph"]),
        ],
        "Dynamic Programming": [
            LCProblem(70, "climbing-stairs", "Climbing Stairs", "Easy", ["DP"]),
            LCProblem(322, "coin-change", "Coin Change", "Medium", ["DP"]),
        ],
    }


def lc_to_json(topic: str, p: LCProblem):
    return {
        "lc_id": p.lc_id,
        "slug": p.slug,
        "title": p.title,
        "difficulty": p.difficulty,
        "topic": topic,
        "url": f"https://leetcode.com/problems/{p.slug}/",
        "tags": p.tags,
    }


def get_recommendations(weak_topics: List[str], solved_slugs: Set[str], limit: int = 15):
    result = []
    bank = lc_bank()

    def add_from_topic(topic, max_diff=None):
        if topic not in bank:
            return
        for p in bank[topic]:
            if len(result) >= limit:
                return
            if p.slug in solved_slugs:
                continue
            if max_diff and p.difficulty != max_diff:
                continue
            result.append(lc_to_json(topic, p))

    for t in weak_topics:
        add_from_topic(t, "Easy")
        add_from_topic(t, "Medium")

    for topic in bank:
        if len(result) >= limit:
            break
        if topic not in weak_topics:
            add_from_topic(topic, "Easy")

    return result