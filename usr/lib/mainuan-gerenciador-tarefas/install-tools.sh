#!/bin/sh
# Instala htop e fastfetch quando faltam. Executado como root.
# Uso: install-tools.sh [ferramenta]   (sem argumento: as três)
TAG="[mainuan-gerenciador-tarefas]"
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -o DPkg::Lock::Timeout=900 -y -q"
WANT="${1:-htop fastfetch}"

have() { command -v "$1" >/dev/null 2>&1; }

missing=""
for p in $WANT; do have "$p" || missing="$missing $p"; done
if [ -z "$missing" ]; then
    echo "$TAG nada a instalar"
    exit 0
fi
echo "$TAG em falta:$missing"

$APT update || echo "$TAG apt update falhou (sem rede?)"
for p in $missing; do
    $APT install "$p" || echo "$TAG $p não está disponível nos repositórios configurados"
done

# fastfetch não existe nos repositórios do Ubuntu 22.04/24.04: usa o PPA oficial do projeto
case " $missing " in
*" fastfetch "*)
    if ! have fastfetch; then
        . /etc/os-release 2>/dev/null || true
        case " $ID $ID_LIKE " in
        *" ubuntu "*)
            echo "$TAG a adicionar o PPA ppa:zhangsongcui3371/fastfetch"
            $APT install software-properties-common || true
            if have add-apt-repository; then
                add-apt-repository -y ppa:zhangsongcui3371/fastfetch && $APT update && $APT install fastfetch
            fi
            ;;
        esac
    fi
    ;;
esac

rc=0
for p in $WANT; do
    if have "$p"; then echo "$TAG $p OK"; else echo "$TAG $p continua em falta"; rc=1; fi
done
exit $rc
