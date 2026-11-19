import { useEffect, useRef, useState } from 'react';
import api from '../../api/config';
import styles from './CancelledRequests.module.css';

function dateLabel(value) {
    if (!value) return 'не указана';
    const [year, month, day] = value.slice(0, 10).split('-');
    return `${day}.${month}.${year}`;
}
function recordedLabel(value) {
    if (!value) return 'не указано';
    const offset = value.match(/([+-]\d{2}:\d{2}|Z)$/)?.[0];
    return `${dateLabel(value)} ${value.slice(11, 16)}${offset ? ` (UTC${offset === 'Z' ? '' : offset})` : ''}`;
}
function errorLabel(error) {
    const data = error.response?.data;
    if (typeof data?.error === 'string') return data.error;
    if (typeof data?.detail === 'string') return data.detail;
    return data
        ? Object.values(data).flat().join(' ')
        : 'Не удалось загрузить данные. Повторите попытку.';
}
const eventLabels = {
    group_cancelled: 'Группа отменена',
    group_archived: 'Заявка архивирована',
    group_restored: 'Заявка восстановлена из архива',
};

function RequestHistory({ id }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        api.get(`/api/execution/director/cancelled-groups/${id}/`, {
            signal: controller.signal,
        })
            .then(({ data: result }) => setData(result))
            .catch((err) => {
                if (!controller.signal.aborted) setError(errorLabel(err));
            });
        return () => controller.abort();
    }, [id]);
    if (error)
        return (
            <p role="alert" className={styles.error}>
                {error}
            </p>
        );
    if (!data) return <p role="status">Загрузка истории…</p>;
    const history = data.history;
    const students = Object.fromEntries(
        history.students.map((row) => [row.id, row.name]),
    );
    return (
        <section className={styles.history} aria-label="История заявки">
            <p className={styles.notice}>
                История доступна только для просмотра. Безвозвратное удаление
                выполняется администратором в Django Admin.
            </p>
            {data.deletion_blockers.length > 0 && (
                <p>
                    Допустимо только архивирование:{' '}
                    {data.deletion_blockers.join(' ')}
                </p>
            )}
            <h3>Слушатели ({history.students.length})</h3>
            {history.students.length ? (
                <ol className={styles.entries}>
                    {history.students.map((row) => (
                        <li key={row.id}>
                            {row.name} — {row.status}
                        </li>
                    ))}
                </ol>
            ) : (
                <p>Слушатели не назначены.</p>
            )}
            <h3>Расписание ({history.schedule.length})</h3>
            {history.schedule.length ? (
                <ul className={styles.entries}>
                    {history.schedule.map((row) => (
                        <li key={row.id}>
                            {dateLabel(row.date)} {row.start_time?.slice(0, 5)}{' '}
                            — {row.end_time?.slice(0, 5)} · {row.section__title}
                            {row.is_completed && ' · Проведено'}
                        </li>
                    ))}
                </ul>
            ) : (
                <p>Занятия не запланированы.</p>
            )}
            <h3>Оценки и замечания ({history.assessments.length})</h3>
            {history.assessments.length ? (
                <ul className={styles.entries}>
                    {history.assessments.map((row) => (
                        <li key={row.id}>
                            <strong>
                                {students[row.enrollment_id]} · {row.section}
                            </strong>
                            <div>
                                Оценка:{' '}
                                {row.score ??
                                    (row.passed
                                        ? 'Зачтено'
                                        : 'не выставлена')}{' '}
                                · {dateLabel(row.date)} ·{' '}
                                {row.instructor || 'Преподаватель не указан'}
                            </div>
                            {row.notes && (
                                <div className={styles.reason}>{row.notes}</div>
                            )}
                        </li>
                    ))}
                </ul>
            ) : (
                <p>Оценок нет.</p>
            )}
            <h3>ПЭП и подтверждения ({history.signatures.length})</h3>
            {history.signatures.length ? (
                <ul className={styles.entries}>
                    {history.signatures.map((row) => (
                        <li key={row.id}>
                            {row.action}
                            <div>{row.signature}</div>
                        </li>
                    ))}
                </ul>
            ) : (
                <p>Подтверждений нет.</p>
            )}
            <h3>Документы об обучении ({history.certificates.length})</h3>
            {history.certificates.length ? (
                <ul>
                    {history.certificates.map((row) => (
                        <li key={row.id}>
                            {row.number} · {dateLabel(row.issue_date)}
                        </li>
                    ))}
                </ul>
            ) : (
                <p>Документы не выдавались.</p>
            )}
            <h3>Отмена и архивирование</h3>
            <ul className={styles.entries}>
                {history.events.map((row) => (
                    <li key={row.id}>
                        {eventLabels[row.details?.operation] ||
                            'Изменение в административной части'}{' '}
                        · {recordedLabel(row.at)} · {row.author}
                        {row.details?.reason && (
                            <div className={styles.reason}>
                                {row.details.reason}
                            </div>
                        )}
                    </li>
                ))}
            </ul>
        </section>
    );
}

function ArchiveDialog({ group, onClose, onDone }) {
    const dialog = useRef(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    useEffect(() => {
        dialog.current.showModal();
    }, []);
    async function submit(event) {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        setError('');
        try {
            const { data } = await api.post(
                `/api/execution/director/cancelled-groups/${group.id}/archive/`,
                { confirm_delete_files: true },
            );
            onDone(data.message);
        } catch (err) {
            setError(errorLabel(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <dialog
            ref={dialog}
            className={styles.dialog}
            aria-labelledby="archive-title"
            onCancel={(event) => {
                event.preventDefault();
                if (!busy) onClose();
            }}
        >
            <form onSubmit={submit}>
                <h2 id="archive-title">Архивировать отменённую заявку?</h2>
                <p>
                    <strong>{group.assigned_number}</strong>
                </p>
                <p>
                    Сформированные файлы будут удалены. Причина и дата отмены,
                    назначения, оценки и ПЭП останутся в базе. При необходимости
                    администратор сможет восстановить заявку в статусе
                    «Отменена».
                </p>
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                <div className={styles.actions}>
                    <button
                        autoFocus
                        type="button"
                        className={styles.button}
                        disabled={busy}
                        onClick={onClose}
                    >
                        Назад
                    </button>
                    <button
                        type="submit"
                        className={styles.primary}
                        disabled={busy}
                    >
                        {busy
                            ? 'Архивирование…'
                            : 'Архивировать и удалить файлы'}
                    </button>
                </div>
            </form>
        </dialog>
    );
}

export default function CancelledRequests() {
    const [filters, setFilters] = useState({
        status: 'cancelled',
        search: '',
        date_from: '',
        date_to: '',
    });
    const [query, setQuery] = useState(filters);
    const [page, setPage] = useState(1);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [expanded, setExpanded] = useState(null);
    const [archiveGroup, setArchiveGroup] = useState(null);
    const [reload, setReload] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        const params = Object.fromEntries(
            Object.entries({ ...query, page }).filter(
                ([, value]) => value !== '',
            ),
        );
        api.get('/api/execution/director/cancelled-groups/', {
            params,
            signal: controller.signal,
        })
            .then(({ data }) => {
                setResult(data);
                setLoading(false);
            })
            .catch((err) => {
                if (!controller.signal.aborted) {
                    setError(errorLabel(err));
                    setLoading(false);
                }
            });
        return () => controller.abort();
    }, [query, page, reload]);
    function apply(event) {
        event.preventDefault();
        setLoading(true);
        setError('');
        setExpanded(null);
        setPage(1);
        setQuery({ ...filters });
    }
    function movePage(value) {
        setLoading(true);
        setError('');
        setExpanded(null);
        setPage(value);
    }
    return (
        <div className={styles.page}>
            <h1>Отменённые заявки</h1>
            <p className={styles.meta}>
                Заявки групп, где вы назначены подписывающим руководителем.
                Период отбора — по фактической дате отмены.
            </p>
            <form className={styles.filters} onSubmit={apply}>
                <label>
                    Статус
                    <select
                        className={styles.field}
                        value={filters.status}
                        onChange={(e) =>
                            setFilters({ ...filters, status: e.target.value })
                        }
                    >
                        <option value="cancelled">Отменённые</option>
                        <option value="archived">В архиве</option>
                        <option value="all">Все отменённые заявки</option>
                    </select>
                </label>
                <label>
                    Дата отмены с
                    <input
                        className={styles.field}
                        type="date"
                        value={filters.date_from}
                        onChange={(e) =>
                            setFilters({
                                ...filters,
                                date_from: e.target.value,
                            })
                        }
                    />
                </label>
                <label>
                    По
                    <input
                        className={styles.field}
                        type="date"
                        min={filters.date_from || undefined}
                        value={filters.date_to}
                        onChange={(e) =>
                            setFilters({ ...filters, date_to: e.target.value })
                        }
                    />
                </label>
                <label>
                    Группа или модуль
                    <input
                        className={styles.field}
                        type="search"
                        maxLength={150}
                        value={filters.search}
                        onChange={(e) =>
                            setFilters({ ...filters, search: e.target.value })
                        }
                    />
                </label>
                <button className={styles.button}>Показать</button>
            </form>
            {notice && (
                <p role="status" className={styles.notice}>
                    {notice}
                </p>
            )}
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {loading ? (
                <p role="status">Загрузка…</p>
            ) : (
                !error && (
                    <>
                        <p>Найдено заявок: {result?.count || 0}</p>
                        {result?.results.map((group) => (
                            <article key={group.id} className={styles.card}>
                                <span className={styles.badge}>
                                    {group.status === 'archived'
                                        ? 'В архиве · отменённая заявка'
                                        : 'Отменена'}
                                </span>
                                <h2>{group.assigned_number}</h2>
                                <p>{group.module_title}</p>
                                <p className={styles.meta}>
                                    План обучения: {dateLabel(group.start_date)}{' '}
                                    — {dateLabel(group.end_date)} · Слушателей:{' '}
                                    {group.students_count}
                                </p>
                                <p>
                                    <strong>Дата отмены:</strong>{' '}
                                    {dateLabel(group.cancellation_date)}
                                </p>
                                <p className={styles.reason}>
                                    <strong>Причина:</strong>{' '}
                                    {group.cancellation_reason ||
                                        'не указана в старой записи'}
                                </p>
                                <p className={styles.meta}>
                                    Зафиксировал:{' '}
                                    {group.cancelled_by || 'не указан'} ·{' '}
                                    {recordedLabel(group.cancelled_at)}
                                </p>
                                <div className={styles.actions}>
                                    <button
                                        className={styles.button}
                                        aria-expanded={expanded === group.id}
                                        onClick={() =>
                                            setExpanded(
                                                expanded === group.id
                                                    ? null
                                                    : group.id,
                                            )
                                        }
                                    >
                                        {expanded === group.id
                                            ? 'Скрыть историю'
                                            : 'Посмотреть историю'}
                                    </button>
                                    {group.status === 'cancelled' && (
                                        <button
                                            className={styles.button}
                                            onClick={() =>
                                                setArchiveGroup(group)
                                            }
                                        >
                                            Архивировать
                                        </button>
                                    )}
                                </div>
                                {expanded === group.id && (
                                    <RequestHistory id={group.id} />
                                )}
                            </article>
                        ))}
                        {result && result.total_pages > 1 && (
                            <nav
                                className={styles.pagination}
                                aria-label="Страницы заявок"
                            >
                                <button
                                    className={styles.button}
                                    disabled={result.page <= 1}
                                    onClick={() => movePage(result.page - 1)}
                                >
                                    Назад
                                </button>
                                <span>
                                    {result.page} из {result.total_pages}
                                </span>
                                <button
                                    className={styles.button}
                                    disabled={result.page >= result.total_pages}
                                    onClick={() => movePage(result.page + 1)}
                                >
                                    Далее
                                </button>
                            </nav>
                        )}
                    </>
                )
            )}
            {archiveGroup && (
                <ArchiveDialog
                    group={archiveGroup}
                    onClose={() => setArchiveGroup(null)}
                    onDone={(message) => {
                        setArchiveGroup(null);
                        setExpanded(null);
                        setNotice(message);
                        setError('');
                        setLoading(true);
                        setReload((value) => value + 1);
                    }}
                />
            )}
        </div>
    );
}
