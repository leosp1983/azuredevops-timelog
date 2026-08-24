"""CLI: orquestra o fluxo completo de log de horas no Azure DevOps."""
from __future__ import annotations

import argparse
from datetime import date

from azuredevops_timelog import azdo_client, timelog_client
from azuredevops_timelog.dates import business_days_in_range, parse_date_range

HOURS_PER_DAY = 4


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Loga horas diárias no Azure DevOps. Sem --from/--to, cobre "
            "retroativamente do dia 1 do mês atual até hoje, validando dia "
            "a dia o que já foi logado e preenchendo só o que falta."
        )
    )
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD (início do range; sobrepõe o default do mês atual)")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD (fim do range; use junto com --from)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra a chamada que seria feita ao TimeLog, sem enviar",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    today = date.today()
    date_range = parse_date_range(args, today=today)
    days = business_days_in_range(date_range.start, date_range.end)

    # Cada pessoa do time descobre a própria identidade a partir do
    # próprio AZDO_PAT — não tem usuário fixo em lugar nenhum do código.
    user = azdo_client.get_current_user()
    print(f"Rodando como {user.name} ({user.email}).")

    # Idempotente e independente do range pedido: sempre confere se a Task
    # do mês anterior a hoje ainda está aberta e fecha, se estiver. Não cria
    # a Task do mês anterior se ela nunca existiu.
    closed_id = azdo_client.close_previous_month_task(today.year, today.month)
    if closed_id is not None:
        print(f"Task do mês anterior fechada automaticamente (ID {closed_id}).")

    if not days:
        print("Nenhum dia útil no range informado (fim de semana/feriado). Nada a fazer.")
        return

    logged, skipped, failed = [], [], []
    task_ids: dict[tuple[int, int], int] = {}

    for day in days:
        month_key = (day.year, day.month)
        if month_key not in task_ids:
            task_ids[month_key] = azdo_client.find_or_create_month_task(*month_key)
        task_id = task_ids[month_key]

        try:
            if timelog_client.entry_exists_for_date(task_id, day, user):
                skipped.append(day)
                continue
            timelog_client.add_time_log_entry(
                task_id, day, HOURS_PER_DAY, user, dry_run=args.dry_run
            )
            if not args.dry_run:
                logged.append(day)
        except Exception as exc:  # segue pros próximos dias em vez de abortar o lote
            print(f"Falhou em {day.isoformat()}: {exc}")
            failed.append(day)

    if args.dry_run:
        print("\n[dry-run] nenhuma chamada real foi enviada.")
    print("\nResumo:")
    print(f"  Logados: {len(logged)} -> {[d.isoformat() for d in logged]}")
    print(f"  Já existiam: {len(skipped)} -> {[d.isoformat() for d in skipped]}")
    print(f"  Falharam: {len(failed)} -> {[d.isoformat() for d in failed]}")
