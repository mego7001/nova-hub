import unittest

from ui.hud_qml.models import DictListModel


class TestHUDModels(unittest.TestCase):
    def test_dict_list_model_lifecycle(self) -> None:
        model = DictListModel(["id", "name"])
        self.assertEqual(model.count(), 0)

        model.set_items([{"id": "a", "name": "Alpha"}])
        self.assertEqual(model.count(), 1)
        self.assertEqual(model.get(0)["name"], "Alpha")

        model.append_item({"id": "b", "name": "Beta"})
        self.assertEqual(model.count(), 2)
        self.assertEqual(model.get(1)["id"], "b")

        model.update_row(1, {"name": "Beta+"})
        self.assertEqual(model.get(1)["name"], "Beta+")

        model.remove_row(0)
        self.assertEqual(model.count(), 1)
        self.assertEqual(model.get(0)["id"], "b")

        model.clear()
        self.assertEqual(model.count(), 0)


if __name__ == "__main__":
    unittest.main()
