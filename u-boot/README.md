# Правки загрузчика

Меню выбора системы живёт в форке u-boot
[mamaich/u-boot-rk3562-rg52mini](https://github.com/mamaich/u-boot-rk3562-rg52mini),
основная ветка `next-dev`, начиная с коммита `0ea01de2e9`. Здесь — те же
коммиты патчами, относительно `3cf51ca414` (выпуск `rg52mini-1.3` и
документация после него):

| Патч | Что делает |
|---|---|
| `0001-rockchip-distro-files-come-from-the-first-bootable-p.patch` | дерево, логотип и картинки зарядки читаются с первого загрузочного раздела, а не со строки из всех сразу (с двумя такими разделами не читалось ничего) |
| `0002-rg52mini-boot-menu-for-a-card-with-GammaOS-and-dArkO.patch` | само меню: `board/rockchip/evb_rk3562/rg52_bootmenu.c`, включается `CONFIG_RG52_BOOTMENU` в `rk3562-rg52mini_defconfig` |
| `0003-rg52mini-bootmenu-also-on-a-power-on.patch` | меню и при включении кнопкой: тогда регистр режима пуст («boot mode: None»), и без этого первым шёл dArkOS, даже до первой настройки GammaOS |

Наложить на свой клон форка:

    git checkout -b menu 3cf51ca414
    git am /путь/к/RG52mini-dualboot/u-boot/*.patch

Как устроено меню и когда оно появляется — в
[../doc/01-устройство.md](../doc/01-устройство.md#загрузка), как собрать
загрузчик — в [../doc/02-сборка.md](../doc/02-сборка.md#2-загрузчик-с-меню).
