import { useEffect, useState } from 'react';
import api from '../../api/config';
import styles from './Instructors.module.css';

const base = '/api/execution/methodist';
function errorText(error) {
    const data = error.response?.data;
    return (
        data?.error ||
        Object.values(data || {})
            .flat()
            .join(' ') ||
        'Не удалось сохранить данные. Повторите попытку.'
    );
}
function MappingRow({ row, references }) {
    const [subject, setSubject] = useState(row.subject || '');
    const [device, setDevice] = useState(row.teaching_device_type || '');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    async function save(event) {
        event.preventDefault();
        setBusy(true);
        setMessage('');
        setError('');
        try {
            const { data } = await api.patch(
                `${base}/instructor-section-mappings/${row.id}/`,
                { subject: Number(subject), teaching_device_type: device },
            );
            setMessage(
                data.message +
                    (data.upcoming_assignments_to_review
                        ? ` Проверьте будущие назначения: ${data.upcoming_assignments_to_review}.`
                        : ''),
            );
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <article className={styles.panel}>
            <h3>{row.title}</h3>
            <p className={styles.meta}>
                {row.module} · {row.module_title}
            </p>
            <form onSubmit={save}>
                <div className={styles.form}>
                    <label>
                        Предмет допуска
                        <select
                            className={styles.field}
                            required
                            disabled={busy}
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                        >
                            <option value="">Выберите предмет</option>
                            {references.subjects.map((item) => (
                                <option key={item.id} value={item.id}>
                                    {item.code} {item.name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label>
                        Формат преподавания
                        <select
                            className={styles.field}
                            required
                            disabled={busy}
                            value={device}
                            onChange={(e) => setDevice(e.target.value)}
                        >
                            <option value="">Выберите формат</option>
                            {references.devices.map((item) => (
                                <option key={item.code} value={item.code}>
                                    {item.name}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
                <div className={styles.actions}>
                    <button className={styles.button} disabled={busy}>
                        {busy ? 'Сохранение…' : 'Сохранить связь'}
                    </button>
                </div>
            </form>
            {message && (
                <p role="status" className={styles.notice}>
                    {message}
                </p>
            )}
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
        </article>
    );
}
export default function TeacherSubjects({ references, onBack, onChanged }) {
    const [name, setName] = useState('');
    const [code, setCode] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [filters, setFilters] = useState({ module: '', search: '' });
    const [query, setQuery] = useState(filters);
    const [page, setPage] = useState(1);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        const controller = new AbortController();
        api.get(`${base}/instructor-section-mappings/`, {
            params: { ...query, page },
            signal: controller.signal,
        })
            .then(({ data }) => {
                setResult(data);
                setLoading(false);
            })
            .catch((err) => {
                if (!controller.signal.aborted) {
                    setError(errorText(err));
                    setLoading(false);
                }
            });
        return () => controller.abort();
    }, [query, page]);
    async function addSubject(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        setNotice('');
        try {
            await api.post(`${base}/instructor-subjects/`, {
                name: name.trim(),
                code: code.trim(),
            });
            setNotice(
                'Предмет добавлен в справочник. Теперь можно связать его с разделами и допусками.',
            );
            setName('');
            setCode('');
            onChanged();
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <div className={styles.page}>
            <button className={styles.button} onClick={onBack}>
                ← К преподавателям
            </button>
            <h1>Предметы и разделы программ</h1>
            <p className={styles.notice}>
                Эти связи используются для проверки допусков преподавателей.
                Названия, содержание, часы программы и существующие назначения
                сохраняются.
            </p>
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {notice && (
                <p role="status" className={styles.notice}>
                    {notice}
                </p>
            )}
            <section className={styles.panel}>
                <h2>Добавить предмет в справочник</h2>
                <form onSubmit={addSubject}>
                    <div className={styles.form}>
                        <label>
                            Название
                            <input
                                className={styles.field}
                                required
                                maxLength={200}
                                disabled={busy}
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                            />
                        </label>
                        <label>
                            Код (если используется)
                            <input
                                className={styles.field}
                                maxLength={50}
                                disabled={busy}
                                value={code}
                                onChange={(e) => setCode(e.target.value)}
                            />
                        </label>
                    </div>
                    <div className={styles.actions}>
                        <button
                            className={styles.primary}
                            disabled={busy || !name.trim()}
                        >
                            {busy ? 'Сохранение…' : 'Добавить предмет'}
                        </button>
                    </div>
                </form>
            </section>
            <h2>Связи разделов с допусками</h2>
            <form
                className={styles.filters}
                onSubmit={(event) => {
                    event.preventDefault();
                    setLoading(true);
                    setError('');
                    setPage(1);
                    setQuery({ ...filters });
                }}
            >
                <label>
                    Программа / модуль
                    <select
                        className={styles.field}
                        value={filters.module}
                        onChange={(e) =>
                            setFilters({ ...filters, module: e.target.value })
                        }
                    >
                        <option value="">Все модули</option>
                        {references.modules.map((row) => (
                            <option key={row.id} value={row.id}>
                                {row.code} · {row.title}
                            </option>
                        ))}
                    </select>
                </label>
                <label>
                    Название раздела
                    <input
                        className={styles.field}
                        type="search"
                        value={filters.search}
                        onChange={(e) =>
                            setFilters({ ...filters, search: e.target.value })
                        }
                    />
                </label>
                <button className={styles.button}>Показать</button>
            </form>
            {loading ? (
                <p role="status">Загрузка…</p>
            ) : (
                <>
                    <p>Разделов: {result?.count || 0}</p>
                    {result?.results.map((row) => (
                        <MappingRow
                            key={row.id}
                            row={row}
                            references={references}
                        />
                    ))}
                    {result && (result.previous || result.next) && (
                        <nav
                            className={styles.pagination}
                            aria-label="Страницы разделов"
                        >
                            <button
                                className={styles.button}
                                disabled={!result.previous}
                                onClick={() => {
                                    setLoading(true);
                                    setPage(page - 1);
                                }}
                            >
                                Назад
                            </button>
                            <span>Страница {page}</span>
                            <button
                                className={styles.button}
                                disabled={!result.next}
                                onClick={() => {
                                    setLoading(true);
                                    setPage(page + 1);
                                }}
                            >
                                Далее
                            </button>
                        </nav>
                    )}
                </>
            )}
        </div>
    );
}
