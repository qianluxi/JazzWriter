"""World Studio: a standalone worldview forge (independent entry + data dir).

Two creative modes:
  * spark  - turn a fragment of an idea into several structurally different worlds
  * graft  - import an existing worldview, extract its skeleton, and transform it
Output is a plain Markdown worldview document.
"""

from world.models import WorldDoc, WorldEntity, WorldIdea
from world.studio import WorldStudio

__all__ = ["WorldStudio", "WorldDoc", "WorldEntity", "WorldIdea"]
