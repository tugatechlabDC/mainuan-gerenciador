# Changelog

Todas as alterações relevantes deste projeto são documentadas neste ficheiro.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-PT/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).


## 🎉 Lançamento [1.0.3] - 2026-11-26

### Adicionado
- Separador **Desempenho** com gráficos em tempo real de CPU, memória, discos, rede e GPU.
- Separador **Processos** com agrupamento por aplicações e processos em segundo plano; finalizar tarefa, finalizar árvore de processos, forçar encerramento (SIGKILL), definir prioridade e afinidade, e abrir o local do ficheiro.
- Separador **Histórico de aplicações** com tempo de CPU, leitura/escrita em disco e pico de memória.
- Separador **Arranque** para ver e ativar/desativar programas de autostart, com impacto estimado.
- Separador **Utilizadores**.
- Separador **Serviços** (systemd) com iniciar, parar e reiniciar.
- Separadores **Fastfetch** e **Htop** integrados na aplicação.
- Velocidade de atualização configurável.
- Idioma detetado automaticamente: pt-PT, pt-BR, inglês, espanhol e francês.
- Ações privilegiadas através do PolicyKit (`pkexec`).
- Instalação automática, em segundo plano, do `htop` e do `fastfetch` quando em falta.

## 👤 Autor

Desenvolvido e mantido por David Caixinha.

## 🤝 Contribuir

Para reportar erros ou pedir funcionalidades:
- **Issues**: https://github.com/mainuan/mainuan-gerenciador/issues
- **Email**: info@mainuanlinux.com
