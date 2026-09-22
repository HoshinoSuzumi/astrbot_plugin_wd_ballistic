"""WARDOGS direct-hit damage calculation backed by the exported data source."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

DATA_PATH = Path(__file__).with_name("data") / "wardogs_ballistics_raw.json"
UNDEFINED = "$undefined"

AMMO_ALIASES = {
    "fmj": "FMJ", "标准": "FMJ", "全被甲": "FMJ",
    "hp": "HollowPoint", "肉弹": "HollowPoint", "肉伤": "HollowPoint", "空尖": "HollowPoint",
    "ap": "ArmorPiercing", "穿甲": "ArmorPiercing", "穿甲弹": "ArmorPiercing",
}
LOCATION_ALIASES = {
    "head": "Head", "头": "Head", "头部": "Head", "neck": "Neck", "颈": "Neck", "脖子": "Neck",
    "torso_upper": "Torso.Upper", "upper": "Torso.Upper", "上躯干": "Torso.Upper",
    "torso_middle": "Torso.Middle", "mid": "Torso.Middle", "中躯干": "Torso.Middle",
    "torso_lower": "Torso.Lower", "lower": "Torso.Lower", "下躯干": "Torso.Lower",
    "pelvis": "Pelvis", "骨盆": "Pelvis", "upper_arm": "Arm.Upper", "上臂": "Arm.Upper",
    "forearm": "Arm.Lower", "前臂": "Arm.Lower", "hand": "Arm.Hand", "手": "Arm.Hand",
    "thigh": "Leg.Thigh", "大腿": "Leg.Thigh", "calf": "Leg.Calf", "小腿": "Leg.Calf",
    "foot": "Leg.Foot", "脚": "Leg.Foot",
}

class DamageQueryError(ValueError): pass

@dataclass(frozen=True)
class DamageResult:
    weapon: str; ammo: str; location: str; range_m: float; damage: float
    shots_to_kill: int; ttk_s: float | None; armor_name: str | None
    factors: tuple[tuple[str, float], ...]
    def format_message(self) -> str:
        lines=[f"{self.weapon} · {self.ammo} · {self.location}", f"距离：{self.range_m:g} m", f"单发伤害：{self.damage:.1f}", "倍率："+" × ".join(f"{k} {v:.2f}" for k,v in self.factors), f"击杀所需：{self.shots_to_kill} 发"]
        if self.armor_name: lines.insert(2, f"护甲：{self.armor_name}")
        lines.append("TTK：数据未提供射速" if self.ttk_s is None else f"TTK：{self.ttk_s:.2f} s")
        return "\n".join(lines)

class DamageCalculator:
    def __init__(self, path: Path = DATA_PATH):
        self.data=json.loads(path.read_text(encoding="utf-8"))
        self.weapons={w["name"].casefold():w for w in self.data["weapons"]}
        self.weapons.update({w.get("slug","").casefold():w for w in self.data["weapons"]})
    def weapon(self, value: str) -> dict:
        key=value.casefold()
        found=self.weapons.get(key)
        if not found: raise DamageQueryError(f"未知武器：{value}")
        return found
    def calculate(self, weapon_name: str, ammo="FMJ", location="Torso.Upper", armor=None, range_m=50, health=100) -> DamageResult:
        w=self.weapon(weapon_name); ammo=AMMO_ALIASES.get(ammo.casefold(), ammo)
        location=LOCATION_ALIASES.get(location.casefold(), location)
        rounds=self.data["roundsByCaliber"].get(w["caliberKey"], [])
        r=next((x for x in rounds if x["ammoType"]==ammo), None)
        if not r: raise DamageQueryError(f"{w['name']} 没有可用弹种：{ammo}")
        universal=self.data["reference"]["hitLocationMultipliers"]["Universal"][location]
        profile=self.data["reference"]["hitLocationMultipliers"][w["hitLocationProfile"]][location]
        ammo_factor={"FMJ":1, "HollowPoint":2, "ArmorPiercing":.8, "Buckshot":1, "Slug":1, "Arrow":1}.get(ammo,1)
        weapon_factor=1+sum(rule.get("amount",0) for rule in w.get("weaponRules",[]) if isinstance(rule.get("amount"), (int,float)))/100
        falloff=self._falloff(w.get("damageFalloff"), float(range_m)); armor_obj=self._armor(armor, location)
        armor_factor=1 if not armor_obj else self._armor_factor(armor_obj, r, ammo)
        damage=r["baseDamage"]*(r.get("pellets") if isinstance(r.get("pellets"),int) else 1)*universal*profile*ammo_factor*weapon_factor*falloff*armor_factor
        rpm=w.get("roundsPerMinute"); ttk=None if not isinstance(rpm,(int,float)) else (math.ceil(float(health)/damage)-1)/(rpm/60)
        return DamageResult(w["name"],ammo,location,float(range_m),damage,math.ceil(float(health)/damage),ttk,armor_obj and armor_obj["name"],(("部位",universal*profile),("弹种",ammo_factor),("武器",weapon_factor),("护甲",armor_factor),("距离",falloff)))
    def _falloff(self, points, distance):
        if not isinstance(points,list): return 1
        if distance<=points[0]["rangeM"]: return points[0]["multiplier"]
        for a,b in zip(points,points[1:]):
            if distance<=b["rangeM"]: return a["multiplier"]+(b["multiplier"]-a["multiplier"])*(distance-a["rangeM"])/(b["rangeM"]-a["rangeM"])
        return points[-1]["multiplier"]
    def _armor(self, token, location):
        if not token or token.casefold() in {"none","无","无甲"}: return None
        key=token.casefold().replace(" ","")
        key=key.replace("一级", "1级").replace("二级", "2级").replace("三级", "3级").replace("四级", "4级")
        is_head=location in {"Head","Neck"}; pool=self.data["helmets"] if is_head else self.data["bodyArmor"]
        for i,item in enumerate(pool,1):
            aliases={item["name"].casefold(), f"helmet{i}",f"头{i}",f"{i}级头",f"armor{i}",f"body{i}",f"甲{i}",f"{i}级甲"}
            if key in aliases:
                # Selecting an item that does not cover the chosen body part
                # has no mitigation in the calculator UI.
                return item if location in item["coveredHitLocations"] else None
        raise DamageQueryError(f"未知或不适用于该部位的护甲：{token}")
    def _armor_factor(self, armor, round_, ammo):
        if armor.get("damageReductionPct")==UNDEFINED: return 1
        reduction=armor["damageReductionPct"]/100
        effectiveness=round_.get("penetrationEffectiveness",1)
        if ammo=="ArmorPiercing":
            arm=(round_.get("armsClassTags") or ["Meta.Damage.Arms.Special"])[0]
            effectiveness=self.data["reference"].get("armorEffectivenessByArmsClass",{}).get("Meta.Damage.AmmoModifier.ArmorPiercing",{}).get(arm,effectiveness)
        return 1-reduction*effectiveness

def parse_damage_arguments(raw: str) -> tuple[str,str,str,str|None,float,float]:
    tokens=raw.split()
    if not tokens: raise DamageQueryError("用法：/wd damage <武器> [弹药] [部位] [护甲] [距离] [生命]")
    weapon=tokens.pop(0); ammo="FMJ"; location="Torso.Upper"; armor=None; numbers=[]
    for token in tokens:
        key=token.casefold()
        if key in AMMO_ALIASES: ammo=AMMO_ALIASES[key]
        elif key in LOCATION_ALIASES: location=LOCATION_ALIASES[key]
        elif key.startswith(("helmet","armor","body","头","甲","1级","2级","3级","4级","一级","二级","三级","四级","吉利")): armor=token
        else:
            try: numbers.append(float(token))
            except ValueError: raise DamageQueryError(f"无法识别参数：{token}")
    if len(numbers)>2: raise DamageQueryError("距离和生命值最多各一个")
    return weapon,ammo,location,armor,numbers[0] if numbers else 50,numbers[1] if len(numbers)>1 else 100
