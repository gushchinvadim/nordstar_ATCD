import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/config';
import styles from './Instructors.module.css';
import TeacherSubjects from './TeacherSubjects';

const base = '/api/execution/methodist';
function errorText(error) {
    const data = error.response?.data;
    if (typeof data?.error === 'string') return data.error;
    return data
        ? Object.entries(data)
              .map(
                  ([key, value]) =>
                      `${key === 'non_field_errors' ? '' : `${key}: `}${Array.isArray(value) ? value.join(' ') : value}`,
              )
              .join(' ')
        : 'Не удалось выполнить действие. Повторите попытку.';
}
function dateLabel(value) {
    return value
        ? value.slice(0, 10).split('-').reverse().join('.')
        : 'не указана';
}
function daysLabel(row) {
    if (!row.is_verified || row.days_left === null) return 'Не подтверждён';
    if (row.days_left < 0) return `Просрочен на ${-row.days_left} дн.`;
    if (row.days_left === 0) return 'Истекает сегодня';
    return `${row.days_left} дн.`;
}
function Dialog({ title, busy, onClose, children }) {
    const dialog = useRef(null);
    useEffect(() => {
        dialog.current.showModal();
    }, []);
    return (
        <dialog
            ref={dialog}
            className={styles.dialog}
            aria-label={title}
            onCancel={(event) => {
                event.preventDefault();
                if (!busy) onClose();
            }}
        >
            <h2>{title}</h2>
            {children}
        </dialog>
    );
}

function QualificationDialog({
    teacher,
    references,
    source,
    mode,
    onClose,
    onSaved,
}) {
    const [form, setForm] = useState({
        subject: source?.subject || '',
        device_type: source?.device_type || 'CLASS',
        certificate_number: mode === 'confirm' ? source.certificate_number : '',
        effective_from:
            mode === 'confirm'
                ? source.effective_from
                : source?.effective_from > teacher.today
                  ? source.effective_from
                  : teacher.today,
        valid_until: '',
        issue_date: mode === 'confirm' ? source.issue_date || '' : '',
        waiver_notes: '',
        reason: '',
    });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const field = (key) => ({
        value: form[key],
        onChange: (e) => setForm({ ...form, [key]: e.target.value }),
        disabled: busy,
        className: styles.field,
    });
    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            const url =
                mode === 'confirm'
                    ? `${base}/qualifications/${source.id}/confirm/`
                    : `${base}/instructors/${teacher.id}/qualifications/`;
            await api.post(url, {
                ...form,
                subject: Number(form.subject),
                issue_date: form.issue_date || null,
                valid_until: form.valid_until || null,
            });
            onSaved();
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    const title =
        mode === 'confirm'
            ? 'Подтвердить сведения о допуске'
            : mode === 'renew'
              ? 'Продлить / заменить документ'
              : 'Добавить предмет преподавания';
    return (
        <Dialog title={title} busy={busy} onClose={onClose}>
            <p>{teacher.full_name}</p>
            <p className={styles.notice}>
                Номер документа и дату окончания внесите вручную по сведениям
                контрагента. Дата окончания действует включительно.
            </p>
            {mode === 'confirm' && source.legacy_expiration_date && (
                <p>
                    Прежде рассчитывалась дата{' '}
                    {dateLabel(source.legacy_expiration_date)}. Она не
                    подтверждает действительность допуска.
                </p>
            )}
            <form onSubmit={submit}>
                <div className={styles.form}>
                    <label>
                        Предмет
                        <select
                            {...field('subject')}
                            disabled={busy || mode !== 'add'}
                            required
                        >
                            <option value="">Выберите предмет</option>
                            {references.subjects.map((row) => (
                                <option key={row.id} value={row.id}>
                                    {row.code} {row.name}
                                </option>
                            ))}
                            {source &&
                                !references.subjects.some(
                                    (row) => row.id === source.subject,
                                ) && (
                                    <option value={source.subject}>
                                        {source.subject_name}
                                    </option>
                                )}
                        </select>
                    </label>
                    <label>
                        Формат преподавания
                        <select
                            {...field('device_type')}
                            disabled={busy || mode !== 'add'}
                        >
                            {references.devices.map((row) => (
                                <option key={row.code} value={row.code}>
                                    {row.name}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label>
                        Номер документа
                        <input
                            {...field('certificate_number')}
                            required={
                                mode !== 'add' || Boolean(form.valid_until)
                            }
                            maxLength={100}
                        />
                    </label>
                    <label>
                        Действителен до (включительно)
                        <input
                            type="date"
                            {...field('valid_until')}
                            required={
                                mode !== 'add' ||
                                Boolean(form.certificate_number.trim())
                            }
                            min={form.effective_from}
                        />
                    </label>
                    <label>
                        Действует с
                        <input
                            type="date"
                            {...field('effective_from')}
                            required
                        />
                    </label>
                    <label>
                        Дата выдачи (если известна)
                        <input type="date" {...field('issue_date')} />
                    </label>
                    <label className={styles.wide}>
                        Примечание
                        <textarea
                            {...field('waiver_notes')}
                            rows={2}
                            maxLength={4000}
                        />
                    </label>
                    {mode === 'renew' && (
                        <label className={styles.wide}>
                            Причина продления / замены
                            <textarea
                                {...field('reason')}
                                required
                                rows={2}
                                maxLength={2000}
                            />
                        </label>
                    )}
                </div>
                {mode === 'add' && (
                    <p className={styles.meta}>
                        Если сведения ещё не получены, оставьте номер и дату
                        окончания пустыми. Допуск будет неподтверждённым.
                    </p>
                )}
                {error && (
                    <p className={styles.error} role="alert">
                        {error}
                    </p>
                )}
                <div className={styles.actions}>
                    <button
                        type="button"
                        className={styles.button}
                        onClick={onClose}
                        disabled={busy}
                    >
                        Назад
                    </button>
                    <button className={styles.primary} disabled={busy}>
                        {busy ? 'Сохранение…' : 'Сохранить'}
                    </button>
                </div>
            </form>
        </Dialog>
    );
}

function RevokeDialog({ row, onClose, onSaved }) {
    const [reason, setReason] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            await api.post(`${base}/qualifications/${row.id}/revoke/`, {
                reason: reason.trim(),
            });
            onSaved();
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <Dialog title="Аннулировать допуск" busy={busy} onClose={onClose}>
            <form onSubmit={submit}>
                <p>
                    {row.subject_name} · {row.device_display}
                </p>
                <p>
                    Допуск будет аннулирован с сегодняшнего дня. История
                    останется в системе. Уже назначенные занятия не удаляются;
                    их потребуется проверить.
                </p>
                <label>
                    Причина
                    <textarea
                        className={styles.field}
                        required
                        rows={3}
                        maxLength={2000}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        disabled={busy}
                    />
                </label>
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                <div className={styles.actions}>
                    <button
                        type="button"
                        className={styles.button}
                        disabled={busy}
                        onClick={onClose}
                    >
                        Назад
                    </button>
                    <button
                        className={styles.primary}
                        disabled={busy || !reason.trim()}
                    >
                        {busy ? 'Сохранение…' : 'Аннулировать с причиной'}
                    </button>
                </div>
            </form>
        </Dialog>
    );
}

function AccountDialog({ teacher, onClose, onSaved }) {
    const [username, setUsername] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [credentials, setCredentials] = useState(null);
    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            const { data } = await api.post(
                `${base}/instructors/${teacher.id}/account/`,
                { confirm: true, username },
            );
            setCredentials(data);
            onSaved();
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <Dialog
            title={
                teacher.username
                    ? 'Сброс пароля преподавателя'
                    : 'Создать учётную запись'
            }
            busy={busy}
            onClose={onClose}
        >
            {credentials ? (
                <>
                    <p className={styles.notice}>
                        Передайте данные преподавателю лично. Временный пароль
                        показывается только в этом окне. При входе будет
                        предложена смена пароля.
                    </p>
                    <p>
                        Логин: <strong>{credentials.username}</strong>
                    </p>
                    <label>
                        Временный пароль
                        <input
                            className={styles.field}
                            readOnly
                            value={credentials.temporary_password}
                        />
                    </label>
                    <div className={styles.actions}>
                        <button className={styles.button} onClick={onClose}>
                            Закрыть
                        </button>
                    </div>
                </>
            ) : (
                <form onSubmit={submit}>
                    <p>{teacher.full_name}</p>
                    {teacher.username ? (
                        <p>
                            Логин: {teacher.username}. Прежний пароль и старые
                            сеансы входа перестанут действовать.
                        </p>
                    ) : (
                        <label>
                            Логин
                            <input
                                className={styles.field}
                                required
                                maxLength={150}
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                disabled={busy}
                            />
                        </label>
                    )}
                    {error && (
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                    )}
                    <div className={styles.actions}>
                        <button
                            type="button"
                            className={styles.button}
                            disabled={busy}
                            onClick={onClose}
                        >
                            Назад
                        </button>
                        <button className={styles.primary} disabled={busy}>
                            {busy
                                ? 'Сохранение…'
                                : teacher.username
                                  ? 'Подтвердить сброс пароля'
                                  : 'Создать учётную запись'}
                        </button>
                    </div>
                </form>
            )}
        </Dialog>
    );
}

const emptyPerson = {
    full_name: '',
    email: '',
    phone: '',
    rauts_id: '',
    organization: '',
    position: '',
    is_active: true,
};
function PersonFields({ form, setForm, references, busy }) {
    const input = (key) => ({
        value: form[key] ?? '',
        onChange: (e) => setForm({ ...form, [key]: e.target.value }),
        disabled: busy,
        className: styles.field,
    });
    return (
        <div className={styles.form}>
            <label className={styles.wide}>
                ФИО
                <input {...input('full_name')} required maxLength={200} />
            </label>
            <label>
                Email
                <input {...input('email')} type="email" maxLength={254} />
            </label>
            <label>
                Телефон
                <input {...input('phone')} maxLength={50} />
            </label>
            <label>
                Организация
                <select {...input('organization')}>
                    <option value="">Не указана</option>
                    {references.organizations.map((row) => (
                        <option key={row.id} value={row.id}>
                            {row.name}
                        </option>
                    ))}
                </select>
            </label>
            <label>
                Должность
                <select {...input('position')}>
                    <option value="">Не указана</option>
                    {references.positions.map((row) => (
                        <option key={row.id} value={row.id}>
                            {row.name}
                        </option>
                    ))}
                </select>
            </label>
            <label>
                ID персонала РАУЦ
                <input {...input('rauts_id')} maxLength={50} />
            </label>
            <label>
                <span>Активность</span>
                <span>
                    <input
                        type="checkbox"
                        checked={form.is_active}
                        disabled={busy}
                        onChange={(e) =>
                            setForm({ ...form, is_active: e.target.checked })
                        }
                    />{' '}
                    Преподаватель активен
                </span>
            </label>
        </div>
    );
}
function personPayload(form) {
    return {
        ...form,
        organization: form.organization || null,
        position: form.position || null,
    };
}

function NewInstructor({ references, onClose, onSaved }) {
    const [form, setForm] = useState(emptyPerson);
    const [existing, setExisting] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            const { data } = await api.post(
                `${base}/instructors/`,
                existing
                    ? { existing_staff_id: Number(existing) }
                    : personPayload(form),
            );
            onSaved(data.id);
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <Dialog title="Добавить преподавателя" busy={busy} onClose={onClose}>
            <form onSubmit={submit}>
                <label>
                    Существующий сотрудник
                    <select
                        className={styles.field}
                        value={existing}
                        disabled={busy}
                        onChange={(e) => setExisting(e.target.value)}
                    >
                        <option value="">Создать нового сотрудника</option>
                        {references.existing_staff.map((row) => (
                            <option key={row.id} value={row.id}>
                                {row.full_name}
                            </option>
                        ))}
                    </select>
                </label>
                {!existing && (
                    <PersonFields
                        form={form}
                        setForm={setForm}
                        references={references}
                        busy={busy}
                    />
                )}
                <p className={styles.meta}>
                    Права методиста, директора и администратора при добавлении
                    преподавателя не назначаются.
                </p>
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                <div className={styles.actions}>
                    <button
                        type="button"
                        className={styles.button}
                        onClick={onClose}
                        disabled={busy}
                    >
                        Назад
                    </button>
                    <button className={styles.primary} disabled={busy}>
                        {busy ? 'Сохранение…' : 'Добавить'}
                    </button>
                </div>
            </form>
        </Dialog>
    );
}

function InstructorCard({ id, references, onBack, onChange }) {
    const [data, setData] = useState(null);
    const [form, setForm] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [dialog, setDialog] = useState(null);
    const [refresh, setRefresh] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        function load() {
            api.get(`${base}/instructors/${id}/`, { signal: controller.signal })
                .then(({ data: result }) => {
                    setData(result);
                    setForm(
                        (previous) =>
                            previous ||
                            Object.fromEntries(
                                Object.keys(emptyPerson).map((key) => [
                                    key,
                                    result[key] ?? emptyPerson[key],
                                ]),
                            ),
                    );
                })
                .catch((err) => {
                    if (!controller.signal.aborted) setError(errorText(err));
                });
        }
        load();
        const timer = setInterval(load, 60000);
        return () => {
            controller.abort();
            clearInterval(timer);
        };
    }, [id, refresh]);
    async function save(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        setNotice('');
        try {
            const { data: result } = await api.patch(
                `${base}/instructors/${id}/`,
                personPayload(form),
            );
            setData(result);
            setNotice('Личные данные сохранены. Назначения и ПЭП сохранены.');
            onChange();
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    function saved() {
        setDialog(null);
        setRefresh((value) => value + 1);
        setNotice('Сведения о допуске сохранены.');
        onChange();
    }
    if (!data || !form)
        return (
            <>
                <button className={styles.button} onClick={onBack}>
                    Назад к списку
                </button>
                <p role={error ? 'alert' : 'status'}>
                    {error || 'Загрузка карточки…'}
                </p>
            </>
        );
    return (
        <>
            <div className={styles.actions}>
                <button className={styles.button} onClick={onBack}>
                    ← К списку преподавателей
                </button>
                <button
                    className={styles.button}
                    onClick={() => setRefresh((value) => value + 1)}
                >
                    Обновить допуски
                </button>
            </div>
            <h1>{data.full_name}</h1>
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
                <h2>Личные данные</h2>
                <form onSubmit={save}>
                    <PersonFields
                        form={form}
                        setForm={setForm}
                        references={references}
                        busy={busy}
                    />
                    <div className={styles.actions}>
                        <button className={styles.primary} disabled={busy}>
                            {busy ? 'Сохранение…' : 'Сохранить изменения'}
                        </button>
                    </div>
                </form>
                <p>Учётная запись: {data.username || 'не создана'}</p>
                {data.can_manage_account && (
                    <button
                        className={styles.button}
                        onClick={() => setDialog({ mode: 'account' })}
                    >
                        {data.username
                            ? 'Сбросить пароль'
                            : 'Создать учётную запись'}
                    </button>
                )}
            </section>
            {data.upcoming_issues.length > 0 && (
                <section className={styles.panel}>
                    <h2>
                        Требуют проверки будущие занятия (
                        {data.upcoming_issues.length})
                    </h2>
                    <p>
                        Назначения сохранены. Проверьте допуски, даты или
                        назначьте другого преподавателя.
                    </p>
                    <ul>
                        {data.upcoming_issues.map((row) => (
                            <li key={row.id}>
                                <Link to={`/groups/${row.group_id}/schedule`}>
                                    {row.group}
                                </Link>{' '}
                                · {dateLabel(row.date)} · {row.section}
                                <div>{row.reason}</div>
                            </li>
                        ))}
                    </ul>
                </section>
            )}
            <section className={styles.panel}>
                <h2>Предметы и допуски</h2>
                <p className={styles.meta}>
                    Остаток дней рассчитан на {dateLabel(data.today)} по времени
                    учебного центра. Сведения обновляются раз в минуту.
                </p>
                <button
                    className={styles.button}
                    onClick={() => setDialog({ mode: 'add' })}
                >
                    Добавить предмет преподавания
                </button>
                {data.qualifications.length === 0 ? (
                    <p>Допуски ещё не добавлены.</p>
                ) : (
                    <div className={styles.tableWrap}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th>Предмет / формат</th>
                                    <th>Документ</th>
                                    <th>Срок действия</th>
                                    <th>Статус / осталось</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.qualifications.map((row) => (
                                    <tr key={row.id}>
                                        <td>
                                            {row.subject_name}
                                            <div className={styles.meta}>
                                                {row.device_display}
                                            </div>
                                        </td>
                                        <td>
                                            {row.certificate_number ||
                                                'Нет сведений'}
                                            {row.issue_date && (
                                                <div className={styles.meta}>
                                                    Выдан{' '}
                                                    {dateLabel(row.issue_date)}
                                                </div>
                                            )}
                                            {row.waiver_notes && (
                                                <p className={styles.reason}>
                                                    {row.waiver_notes}
                                                </p>
                                            )}
                                        </td>
                                        <td>
                                            С {dateLabel(row.effective_from)}
                                            <br />
                                            По {dateLabel(row.valid_until)}
                                            {!row.is_verified &&
                                                row.legacy_expiration_date && (
                                                    <p className={styles.meta}>
                                                        Прежний расчёт:{' '}
                                                        {dateLabel(
                                                            row.legacy_expiration_date,
                                                        )}
                                                        . Требует подтверждения.
                                                    </p>
                                                )}
                                        </td>
                                        <td>
                                            <span
                                                className={`${styles.badge} ${styles[row.status] || ''}`}
                                            >
                                                {row.status_display}
                                            </span>
                                            <p>{daysLabel(row)}</p>
                                            {row.revocation_reason && (
                                                <p className={styles.reason}>
                                                    {row.revocation_reason}
                                                </p>
                                            )}
                                        </td>
                                        <td>
                                            {row.is_active ? (
                                                <div className={styles.actions}>
                                                    {!row.is_verified && (
                                                        <button
                                                            className={
                                                                styles.button
                                                            }
                                                            onClick={() =>
                                                                setDialog({
                                                                    mode: 'confirm',
                                                                    source: row,
                                                                })
                                                            }
                                                        >
                                                            Подтвердить сведения
                                                        </button>
                                                    )}
                                                    <button
                                                        className={
                                                            styles.button
                                                        }
                                                        onClick={() =>
                                                            setDialog({
                                                                mode: 'renew',
                                                                source: row,
                                                            })
                                                        }
                                                    >
                                                        Продлить / заменить
                                                    </button>
                                                    <button
                                                        className={
                                                            styles.button
                                                        }
                                                        onClick={() =>
                                                            setDialog({
                                                                mode: 'revoke',
                                                                source: row,
                                                            })
                                                        }
                                                    >
                                                        Аннулировать
                                                    </button>
                                                </div>
                                            ) : (
                                                <span className={styles.meta}>
                                                    История сохранена
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
            {dialog && ['add', 'renew', 'confirm'].includes(dialog.mode) && (
                <QualificationDialog
                    teacher={data}
                    references={references}
                    mode={dialog.mode}
                    source={dialog.source}
                    onClose={() => setDialog(null)}
                    onSaved={saved}
                />
            )}
            {dialog?.mode === 'revoke' && (
                <RevokeDialog
                    row={dialog.source}
                    onClose={() => setDialog(null)}
                    onSaved={saved}
                />
            )}
            {dialog?.mode === 'account' && (
                <AccountDialog
                    teacher={data}
                    onClose={() => setDialog(null)}
                    onSaved={() => {
                        setRefresh((value) => value + 1);
                        onChange();
                    }}
                />
            )}
        </>
    );
}

export default function Instructors() {
    const [manageSubjects, setManageSubjects] = useState(false);
    const [references, setReferences] = useState(null);
    const [result, setResult] = useState(null);
    const [filters, setFilters] = useState({
        search: '',
        state: 'all',
        active: 'all',
        subject: '',
    });
    const [query, setQuery] = useState(filters);
    const [page, setPage] = useState(1);
    const [selected, setSelected] = useState(null);
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const [reload, setReload] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        api.get(`${base}/instructors/references/`, {
            signal: controller.signal,
        })
            .then(({ data }) => setReferences(data))
            .catch((err) => {
                if (!controller.signal.aborted) setError(errorText(err));
            });
        return () => controller.abort();
    }, [reload]);
    useEffect(() => {
        const controller = new AbortController();
        api.get(`${base}/instructors/`, {
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
    }, [query, page, reload]);
    function apply(event) {
        event.preventDefault();
        setError('');
        setLoading(true);
        setPage(1);
        setQuery({ ...filters });
    }
    function refreshList() {
        setReload((value) => value + 1);
    }
    if (manageSubjects && references)
        return (
            <TeacherSubjects
                references={references}
                onBack={() => setManageSubjects(false)}
                onChanged={refreshList}
            />
        );
    if (selected && references)
        return (
            <div className={styles.page}>
                <InstructorCard
                    key={selected}
                    id={selected}
                    references={references}
                    onBack={() => {
                        setSelected(null);
                        refreshList();
                    }}
                    onChange={refreshList}
                />
            </div>
        );
    return (
        <div className={styles.page}>
            <h1>Преподаватели</h1>
            <p className={styles.meta}>
                Личные данные, предметы преподавания и сроки действия допусков.
            </p>
            {error && (
                <p className={styles.error} role="alert">
                    {error}
                </p>
            )}
            {references && (
                <>
                    <div className={styles.actions}>
                        <button
                            className={styles.primary}
                            onClick={() => setAdding(true)}
                        >
                            Добавить преподавателя
                        </button>
                        <button
                            className={styles.button}
                            onClick={() => setManageSubjects(true)}
                        >
                            Предметы и разделы программ
                        </button>
                    </div>
                    <form className={styles.filters} onSubmit={apply}>
                        <label>
                            Поиск
                            <input
                                className={styles.field}
                                type="search"
                                value={filters.search}
                                onChange={(e) =>
                                    setFilters({
                                        ...filters,
                                        search: e.target.value,
                                    })
                                }
                            />
                        </label>
                        <label>
                            Предмет
                            <select
                                className={styles.field}
                                value={filters.subject}
                                onChange={(e) =>
                                    setFilters({
                                        ...filters,
                                        subject: e.target.value,
                                    })
                                }
                            >
                                <option value="">Все предметы</option>
                                {references.subjects.map((row) => (
                                    <option key={row.id} value={row.id}>
                                        {row.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label>
                            Допуски
                            <select
                                className={styles.field}
                                value={filters.state}
                                onChange={(e) =>
                                    setFilters({
                                        ...filters,
                                        state: e.target.value,
                                    })
                                }
                            >
                                <option value="all">Все</option>
                                <option value="unconfirmed">
                                    Не подтверждены
                                </option>
                                <option value="expired">Просрочены</option>
                                <option value="30">Истекают за 30 дней</option>
                                <option value="90">Истекают за 90 дней</option>
                            </select>
                        </label>
                        <label>
                            Преподаватель
                            <select
                                className={styles.field}
                                value={filters.active}
                                onChange={(e) =>
                                    setFilters({
                                        ...filters,
                                        active: e.target.value,
                                    })
                                }
                            >
                                <option value="all">Все</option>
                                <option value="true">Активные</option>
                                <option value="false">Неактивные</option>
                            </select>
                        </label>
                        <button className={styles.button}>Показать</button>
                    </form>
                </>
            )}
            {loading ? (
                <p role="status">Загрузка…</p>
            ) : (
                !error && (
                    <>
                        <p>Найдено: {result?.count || 0}</p>
                        <div className={styles.grid}>
                            {result?.results.map((row) => (
                                <article className={styles.card} key={row.id}>
                                    <h2>{row.full_name}</h2>
                                    <p>
                                        {row.organization_name}{' '}
                                        {row.position_name}
                                    </p>
                                    <p>
                                        {row.is_active
                                            ? 'Активен'
                                            : 'Неактивен'}{' '}
                                        · Предметов/форматов:{' '}
                                        {row.qualification_count}
                                    </p>
                                    <p>
                                        Требуют подтверждения:{' '}
                                        {row.unconfirmed_count}
                                    </p>
                                    <p>
                                        Ближайшее окончание:{' '}
                                        {dateLabel(row.nearest_expiry)}
                                    </p>
                                    <button
                                        className={styles.button}
                                        onClick={() => setSelected(row.id)}
                                    >
                                        Открыть карточку
                                    </button>
                                </article>
                            ))}
                        </div>
                        {result && (result.next || result.previous) && (
                            <nav
                                className={styles.pagination}
                                aria-label="Страницы преподавателей"
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
                )
            )}
            {adding && references && (
                <NewInstructor
                    references={references}
                    onClose={() => setAdding(false)}
                    onSaved={(id) => {
                        setAdding(false);
                        setSelected(id);
                        refreshList();
                    }}
                />
            )}
        </div>
    );
}
