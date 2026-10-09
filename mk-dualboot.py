#!/usr/bin/env python3
"""Единый образ SD-карты RG52 Mini: GammaOS Next + dArkOS + меню выбора в u-boot.

    python3 -I mk-dualboot.py --gamma GAMMA.img --darkos DARKOS.img \
                              --uboot uboot.img [ключи]

Работает без root: только dd, sgdisk и mtools по файлам образов (Linux или
WSL; результат лучше собирать на родной файловой системе Linux, а не на
/mnt/c — так в разы быстрее). Исходные образы не меняются.

Ключи:
    --gamma IMG     образ карты GammaOS Next для RG52 Mini (распакованный .img)
    --darkos IMG    образ карты dArkOS для RG52 Mini
    --uboot IMG     u-boot с меню, 4 МиБ (uboot.img из сборки форка u-boot)
    --menu DIR      кадры меню bootmenu*_*.bmp (по умолчанию menu/out рядом
                    со скриптом)
    --head gamma|darkos
                    откуда взять сектора 34..16383 (idbloader с инициализацией
                    памяти и хранилище Rockchip); по умолчанию gamma — там
                    заводской idbloader
    --out IMG       куда собрать (по умолчанию ./RG52Mini-dualboot-<дата>.img)
    --publish DIR   после сборки скопировать образ туда же с файлом .sha256

У владельца проекта пути по умолчанию свои (если файлы на месте, ключи
--gamma/--darkos/--uboot можно не давать) — см. OWNER_DEFAULTS.

Разметка (номер: имя, в порядке на карте):
    p1  uboot        u-boot с меню                         сектор 16384
    p2  resource     пустой                                сектор 24576
    p3  darkos_boot  FAT dArkOS, единственный bootable:     сектор 32768
                     отсюда u-boot берёт своё дерево, логотип и кадры меню
    p4  rootfs       btrfs dArkOS
    p5  dArkOS_Fat   FAT GammaOS (это имя пишет её OTA)
    p6  system, p7 vendor, p8 cache, p10 metadata, p11 misc — Android
    p9  userdata     Android, физически последний: растягивается до конца
                     карты при первом запуске GammaOS

dArkOS обращается к своим разделам по номерам (mmcblk1p3/p4), Android — только
по именам (/dev/block/by-name), поэтому номера p3/p4 оставлены за dArkOS, а у
Android могут быть любые.
"""
import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
ALIGN = 2048                    # 1 МиБ
SECTOR = 512
HEAD_FIRST, HEAD_END = 34, 16384    # за GPT и до раздела uboot

# Где лежат исходники у владельца проекта: используются, только если
# соответствующий ключ не задан и файлы на месте.
OWNER_DEFAULTS = {
    "gamma": os.path.join(HOME, "rg52/gamma/out/GammaOSCore-*.img"),
    "darkos": "/mnt/t/Dump/RG52Mini/dArkOS/img/dArkOS_*.img",
    # тот же образ, что идёт в выпуски GammaOS Next (с v1.9): её обновление
    # по воздуху перезаписывает раздел uboot
    "uboot": "/mnt/t/Dump/RG52Mini/u-boot/build/uboot-menu-oc.img",
}

# GUID типа "Linux filesystem" — для разделов, у которых нет источника
LINUX_FS = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"

FLAG_TEXT = """\
This card carries two systems: dArkOS (this partition, mmcblk1p3/p4) and
GammaOS Next (Android). U-Boot shows a menu at power-on.
dArkOS: do not repartition the card, ROMs live in Android userdata
(media/0/ROMs). Built by mk-dualboot.py.
"""


def run(*cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def out(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True,
                          text=True).stdout


def pick(value, key):
    """Ключ командной строки, а без него — самый свежий файл владельца."""
    if value:
        if not os.path.isfile(value):
            sys.exit(f"нет файла {value}")
        return value
    files = sorted(glob.glob(OWNER_DEFAULTS[key]), key=os.path.getmtime)
    if not files:
        sys.exit(f"не задан --{key}")
    return files[-1]


def parts(img):
    """{имя: {start, size, type, uuid, attrs, num}} по GPT образа."""
    t = json.loads(out("sfdisk", "-J", img))["partitiontable"]
    res = {}
    for p in t["partitions"]:
        num = int(p["node"][len(img):])
        res[p["name"]] = dict(start=p["start"], size=p["size"],
                              type=p["type"], uuid=p["uuid"],
                              attrs=p.get("attrs", ""), num=num)
    return res


def align_up(x):
    return (x + ALIGN - 1) // ALIGN * ALIGN


def copy(src, src_start, dst, dst_start, count):
    """Сектора src[src_start:+count] -> dst[dst_start:], с сохранением дыр."""
    run("dd", f"if={src}", f"of={dst}", "bs=4M", "status=none",
        "conv=notrunc,sparse", "iflag=skip_bytes,count_bytes",
        "oflag=seek_bytes", f"skip={src_start * SECTOR}",
        f"seek={dst_start * SECTOR}", f"count={count * SECTOR}")


def legacy_darkos_fix(fat, workdir):
    """Подложить dualboot-скрипт первого запуска в старый образ dArkOS.

    Сборки dArkOS до поддержки dualboot (10072026 и раньше) на первом запуске
    удаляют и пересоздают p5 — на общей карте это FAT GammaOS. Если скрипт на
    p3 про dualboot не знает, берём его из ветки dualboot (или master, когда
    её сольют) репозитория dArkOS и делаем fstab.dualboot из fstab.exfat без
    строк про p5. Службы darkos-androidroms в таком rootfs нет, так что
    /roms останется пустым — это только чтобы карту можно было проверить.
    """
    script = subprocess.run(["mtype", "-i", fat, "::/expandtoexfat.sh"],
                            capture_output=True).stdout
    if not script or b"dualboot" in script:
        return
    repo = os.path.join(HOME, "rg52/dArkOS_rg52mini")
    new = None
    for ref in ("master", "dualboot"):
        r = subprocess.run(["git", "-C", repo, "show",
                            f"{ref}:scripts/expandtoexfat.sh.rk3562"],
                           capture_output=True)
        if r.returncode == 0 and b"dualboot" in r.stdout:
            new = r.stdout
            break
    if new is None:
        sys.exit("образ dArkOS старше поддержки общей карты: на первом запуске он "
                 "удалил бы раздел GammaOS. Нужна dArkOS 1.0 (сборка 10082026) или новее")
    fstab = subprocess.run(["mtype", "-i", fat, "::/fstab.exfat"],
                           capture_output=True, check=True).stdout.decode()
    fstab = "".join(l for l in fstab.splitlines(True)
                    if "mmcblk1p5" not in l and "/roms/tools" not in l)
    s = os.path.join(workdir, "expandtoexfat.sh")
    f = os.path.join(workdir, "fstab.dualboot")
    with open(s, "wb") as fh:
        fh.write(new)
    with open(f, "w") as fh:
        fh.write(fstab)
    run("mcopy", "-o", "-i", fat, s, "::/expandtoexfat.sh")
    run("mcopy", "-o", "-i", fat, f, "::/fstab.dualboot")
    os.remove(s)
    os.remove(f)
    print(f"   !! dArkOS без поддержки dualboot: скрипт первого запуска взят из {ref}, "
          "ромы из Android в этой сборке не подключатся")


def main():
    sys.stdout.reconfigure(line_buffering=True)     # ход сборки виден в логе сразу
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gamma")
    ap.add_argument("--darkos")
    ap.add_argument("--uboot")
    ap.add_argument("--menu", default=os.path.join(HERE, "menu/out"))
    ap.add_argument("--head", choices=("darkos", "gamma"), default="gamma")
    ap.add_argument("--out")
    ap.add_argument("--publish")
    a = ap.parse_args()

    gamma = pick(a.gamma, "gamma")
    darkos = pick(a.darkos, "darkos")
    a.uboot = pick(a.uboot, "uboot")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    dst = os.path.abspath(a.out or f"RG52Mini-dualboot-{stamp}.img")
    menu = sorted(glob.glob(os.path.join(a.menu, "bootmenu*_*.bmp")))

    if os.path.getsize(a.uboot) != 4 << 20:
        sys.exit(f"{a.uboot}: ожидается образ u-boot ровно 4 МиБ")
    if len(menu) != 10:
        sys.exit(f"в {a.menu} должно быть 10 кадров bootmenu*_*.bmp, есть {len(menu)}")

    D, G = parts(darkos), parts(gamma)
    for name in ("dArkOS_Fat", "rootfs"):
        if name not in D:
            sys.exit(f"{darkos}: нет раздела {name}")
    for name in ("dArkOS_Fat", "system", "vendor", "cache", "metadata",
                 "misc", "userdata"):
        if name not in G:
            sys.exit(f"{gamma}: нет раздела {name}")

    print(f"dArkOS:  {darkos}")
    print(f"GammaOS: {gamma}")
    print(f"u-boot:  {a.uboot}")
    print(f"выход:   {dst}\n")

    # (номер, имя в GPT, образ-источник, раздел-источник)
    layout = [
        (3, "darkos_boot", darkos, D["dArkOS_Fat"]),
        (4, "rootfs", darkos, D["rootfs"]),
        (5, "dArkOS_Fat", gamma, G["dArkOS_Fat"]),
        (6, "system", gamma, G["system"]),
        (7, "vendor", gamma, G["vendor"]),
        (8, "cache", gamma, G["cache"]),
        (10, "metadata", gamma, G["metadata"]),
        (11, "misc", gamma, G["misc"]),
        (9, "userdata", gamma, G["userdata"]),
    ]
    # p3 обязан начинаться там же, где в обоих исходниках: 32768
    pos = 32768
    plan = []
    for num, name, src, p in layout:
        pos = align_up(pos)
        plan.append((num, name, src, p, pos))
        pos += p["size"]
    total = pos + 34                    # резервная копия GPT

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    with open(dst, "wb") as f:
        f.truncate(total * SECTOR)

    head_src = gamma if a.head == "gamma" else darkos
    print(f"== голова (сектора {HEAD_FIRST}..{HEAD_END - 1}) из {os.path.basename(head_src)}")
    copy(head_src, HEAD_FIRST, dst, HEAD_FIRST, HEAD_END - HEAD_FIRST)

    print("== таблица разделов")
    args = ["sgdisk", "-o", "-U", "R"]
    args += ["-n", "1:16384:24575", "-c", "1:uboot", "-t", f"1:{D['uboot']['type'] if 'uboot' in D else LINUX_FS}"]
    args += ["-n", "2:24576:32767", "-c", "2:resource", "-t", f"2:{D['resource']['type'] if 'resource' in D else LINUX_FS}"]
    for num, name, src, p, start in plan:
        args += ["-n", f"{num}:{start}:{start + p['size'] - 1}",
                 "-c", f"{num}:{name}", "-t", f"{num}:{p['type']}",
                 "-u", f"{num}:{p['uuid']}"]
    args += ["-A", "3:set:2", dst]
    run(*args, stdout=subprocess.DEVNULL)

    print("== u-boot")
    copy(a.uboot, 0, dst, 16384, 8192)

    for num, name, src, p, start in plan:
        if name == "userdata":
            # Android отформатирует его сам при первом запуске (formattable);
            # раздел в образе — нули, их даёт разреженный файл.
            print(f"== p{num} {name}: пустой, {p['size'] * SECTOR >> 20} МиБ")
            continue
        print(f"== p{num} {name} <- {os.path.basename(src)}:{p['num']} "
              f"({p['size'] * SECTOR >> 20} МиБ)")
        copy(src, p["start"], dst, start, p["size"])

    print("== кадры меню и флаг dualboot на p3")
    fat3 = f"{dst}@@{plan[0][4] * SECTOR}"
    for bmp in menu:
        run("mcopy", "-o", "-i", fat3, bmp, "::/")
    flag = os.path.join(os.path.dirname(dst), "dualboot.flag")
    with open(flag, "w") as f:
        f.write(FLAG_TEXT)
    run("mcopy", "-o", "-i", fat3, flag, "::/dualboot")
    os.remove(flag)
    legacy_darkos_fix(fat3, os.path.dirname(dst))

    print("\n== проверки")
    print(out("sgdisk", "-v", dst).strip().splitlines()[-1])
    print(out("sgdisk", "-p", dst).split("Number")[1])
    for num, name, _, _, start in plan:
        if name in ("darkos_boot", "dArkOS_Fat"):
            print(f"p{num} {name}:")
            print(out("mdir", "-w", "-i", f"{dst}@@{start * SECTOR}", "::/"))

    print(f"\nготово: {dst} ({total * SECTOR / 2**30:.2f} ГиБ)")

    sha = out("sha256sum", dst).split()[0]
    with open(dst + ".sha256", "w") as f:
        f.write(f"{sha}  {os.path.basename(dst)}\n")
    print(f"sha256 {sha}")

    if a.publish:
        os.makedirs(a.publish, exist_ok=True)
        pub = os.path.join(a.publish, os.path.basename(dst))
        print(f"== копирую в {pub}")
        run("cp", "--sparse=always", dst, pub)
        run("cp", dst + ".sha256", pub + ".sha256")


if __name__ == "__main__":
    main()
