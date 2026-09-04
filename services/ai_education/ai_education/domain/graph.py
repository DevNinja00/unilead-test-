"""Competency graph structure: directed acyclic prerequisite graph.

Edges are encoded on each ``CompetencyNode`` via ``parent_ids`` (a node's
prerequisites). The graph indexes nodes by id and resolves prerequisite
relationships without mutating the frozen node models.
"""

from collections import deque
from typing import Dict, Iterable, List, Optional, Set

from ai_education.domain.models import CompetencyNode


class CompetencyGraph:
    """A DAG of ``CompetencyNode`` keyed by ``node_id``.

    Edge convention: ``parent_ids`` on a node reference prerequisite nodes.
    A node is "unblocked" for a learner when all of its parents have been
    completed.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, CompetencyNode] = {}

    @property
    def nodes(self) -> List[CompetencyNode]:
        """All nodes in insertion order."""
        return list(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes

    def _require_node(self, node_id: str) -> CompetencyNode:
        if node_id not in self._nodes:
            raise KeyError(f"Unknown competency node id: {node_id!r}")
        return self._nodes[node_id]

    def _parents_of(self, node: CompetencyNode) -> List[CompetencyNode]:
        missing = [pid for pid in node.parent_ids if pid not in self._nodes]
        if missing:
            raise ValueError(
                f"Node {node.id!r} references unknown prerequisites: {missing}"
            )
        return [self._nodes[pid] for pid in node.parent_ids]

    def add_node(self, node: CompetencyNode) -> None:
        """Add or replace a node by its ``id``."""
        if node.id in self._nodes:
            raise ValueError(f"Node already present: {node.id!r}")
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[CompetencyNode]:
        """Return the node with the given id, or ``None`` if absent."""
        return self._nodes.get(node_id)

    def get_prerequisites(self, node_id: str) -> List[CompetencyNode]:
        """Return the direct prerequisite nodes of ``node_id``."""
        return self._parents_of(self._require_node(node_id))

    def get_all_ancestors(self, node_id: str) -> List[CompetencyNode]:
        """Return every prerequisite node reachable from ``node_id``.

        Traverses the full prerequisite tree (parent, grandparent, ...)
        using breadth-first search. Result order is deterministic.
        """
        seed = self._require_node(node_id)
        seen: Set[str] = set()
        ordered: List[CompetencyNode] = []
        queue: deque = deque(self._parents_of(seed))
        while queue:
            current = queue.popleft()
            if current.id in seen:
                continue
            seen.add(current.id)
            ordered.append(current)
            queue.extend(self._parents_of(current))
        return ordered

    def validate_dag(self) -> bool:
        """Return ``True`` if the graph is a valid DAG.

        Valid means: acyclic AND every ``parent_ids`` reference resolves to a
        registered node. Uses Kahn's algorithm (iterative, no recursion).
        """
        in_degree: Dict[str, int] = {}
        children: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        for node in self._nodes.values():
            try:
                parents = self._parents_of(node)
            except ValueError:
                return False
            in_degree[node.id] = len(parents)
            for parent in parents:
                children[parent.id].append(node.id)

        ready = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort()
        queue: deque = deque(ready)
        processed = 0
        while queue:
            current = queue.popleft()
            processed += 1
            for child_id in children[current]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
        return processed == len(self._nodes)

    def get_unblocked_nodes(self, completed_node_ids: Set[str]) -> List[CompetencyNode]:
        """Return nodes whose prerequisites are all satisfied.

        A node is unblocked when it has not yet been completed AND every id
        in its ``parent_ids`` is present in ``completed_node_ids``. Results
        preserve graph insertion order.
        """
        unblocked: List[CompetencyNode] = []
        for node in self._nodes.values():
            if node.id in completed_node_ids:
                continue
            if all(pid in completed_node_ids for pid in node.parent_ids):
                unblocked.append(node)
        return unblocked