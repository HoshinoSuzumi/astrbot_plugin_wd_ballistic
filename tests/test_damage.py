import pytest
from damage import DamageCalculator, parse_damage_arguments

def test_calculates_ui_verified_a91_fmj_upper_torso():
    result = DamageCalculator().calculate("a91")
    assert result.damage == pytest.approx(30.8)
    assert result.shots_to_kill == 4
    assert result.ttk_s == pytest.approx(0.257, abs=.01)

def test_supports_chinese_ammo_location_and_helmet_aliases():
    args = parse_damage_arguments("m4 穿甲弹 头部 四级头 100 100")
    result = DamageCalculator().calculate(*args)
    assert result.ammo == "ArmorPiercing"
    assert result.armor_name == "4 级头盔"
    assert result.damage > 0

def test_hp_alias_is_hollow_point():
    result = DamageCalculator().calculate(*parse_damage_arguments("m4 肉伤 上躯干"))
    assert result.ammo == "HollowPoint"
    assert result.damage == pytest.approx(61.6)

def test_describes_weapon_and_armour_using_localized_aliases():
    calculator = DamageCalculator()
    assert "武器：M4" in calculator.describe("m4")
    helmet = calculator.describe("四级头")
    assert "头盔：4 级头盔" in helmet
    assert "减伤：65%" in helmet
    assert "防弹衣：3 级防弹衣" in calculator.describe("armor3")

def test_lists_equipment_by_category_or_all():
    calculator = DamageCalculator()
    assert "M4" in calculator.list_equipment("武器")
    assert "4 级头盔" in calculator.list_equipment("头盔")
    all_equipment = calculator.list_equipment()
    assert "武器：" in all_equipment and "防弹衣：" in all_equipment
