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
