class AbstractDiffCalculator:
    def is_diffing(self, virtual_address: int) -> bool:
        pass

class NoDiffCalculator(AbstractDiffCalculator):
    def is_diffing(self, virtual_address: int) -> bool:
        return False

class LinkedDiffCalculator(AbstractDiffCalculator):
    def is_diffing(self, virtual_address: int) -> bool:
        # TODO 
        return False