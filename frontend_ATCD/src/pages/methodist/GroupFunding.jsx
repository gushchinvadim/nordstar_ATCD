import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../api/config';
import FundingFields from '../../components/FundingFields';
import { emptyFunding, fundingValue } from '../../components/fundingUtils';
import styles from './Instructors.module.css';

function errorText(error) {
    const data = error.response?.data;
    if (data?.error) return data.error;
    if (data?.detail) return data.detail;
    return data
        ? Object.values(data)
              .flat()
              .map((value) =>
                  typeof value === 'object'
                      ? Object.values(value).flat().join(' ')
                      : value,
              )
              .join(' ')
        : 'Не удалось сохранить финансирование. Повторите попытку.';
}
export default function GroupFunding() {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [group, setGroup] = useState(null);
    const [rows, setRows] = useState([]);
    const [common, setCommon] = useState(emptyFunding);
    const [reason, setReason] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        api.get(`/api/execution/methodist/groups/${groupId}/funding/`, {
            signal: controller.signal,
        })
            .then(({ data }) => {
                setGroup(data);
                setRows(data.enrollments);
                const first =
                    data.enrollments[0] && fundingValue(data.enrollments[0]);
                if (
                    first &&
                    data.enrollments.every(
                        (row) =>
                            JSON.stringify(fundingValue(row)) ===
                            JSON.stringify(first),
                    )
                )
                    setCommon(first);
            })
            .catch((err) => {
                if (!controller.signal.aborted) setError(errorText(err));
            });
        return () => controller.abort();
    }, [groupId]);
    const changed =
        group &&
        JSON.stringify(rows.map(fundingValue)) !==
            JSON.stringify(group.enrollments.map(fundingValue));
    const historical =
        group &&
        (['completed', 'archived', 'cancelled'].includes(group.status) ||
            rows.some((row) => row.status === 'completed'));
    async function save(event) {
        event.preventDefault();
        if (busy) return;
        setBusy(true);
        setError('');
        setNotice('');
        try {
            const { data } = await api.post(
                `/api/execution/methodist/groups/${groupId}/funding/`,
                {
                    reason: reason.trim(),
                    enrollments: rows.map((row) => ({
                        id: row.id,
                        ...fundingValue(row),
                    })),
                },
            );
            setGroup((previous) => ({ ...previous, enrollments: rows }));
            setNotice(data.message);
            setReason('');
        } catch (err) {
            setError(errorText(err));
        } finally {
            setBusy(false);
        }
    }
    return (
        <div className={styles.page}>
            <button
                className={styles.button}
                onClick={() => navigate('/groups')}
            >
                ← К группам
            </button>
            <h1>Финансирование обучения</h1>
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
            {!group ? (
                !error && <p role="status">Загрузка…</p>
            ) : (
                <>
                    <p>
                        {group.assigned_number} · {group.status_display}
                    </p>
                    <p>{group.module}</p>
                    <p className={styles.notice}>
                        Сведения сохраняются отдельно у каждого слушателя.
                        Назначения, оценки, ПЭП и даты обучения сохраняются. Это
                        источник финансирования, а не отметка о поступлении
                        денег.
                    </p>
                    <section className={styles.panel}>
                        <h2>Общий вариант для заполнения</h2>
                        <FundingFields
                            value={common}
                            references={group}
                            onChange={setCommon}
                            disabled={busy}
                        />
                        <button
                            type="button"
                            className={styles.button}
                            disabled={busy || !rows.length}
                            onClick={() =>
                                setRows((previous) =>
                                    previous.map((row) => ({
                                        ...row,
                                        ...common,
                                    })),
                                )
                            }
                        >
                            Применить ко всем слушателям
                        </button>
                        <p className={styles.meta}>
                            После применения можно изменить сведения у отдельных
                            слушателей. Данные сохранятся только после нажатия
                            «Сохранить финансирование».
                        </p>
                    </section>
                    {rows.length ? (
                        <form onSubmit={save}>
                            {rows.map((row, index) => (
                                <section key={row.id} className={styles.panel}>
                                    <h2>
                                        {row.number_in_group}.{' '}
                                        {row.student_name}
                                    </h2>
                                    <p>{row.status_display}</p>
                                    <FundingFields
                                        value={fundingValue(row)}
                                        references={group}
                                        disabled={busy}
                                        onChange={(value) =>
                                            setRows((previous) =>
                                                previous.map(
                                                    (entry, current) =>
                                                        current === index
                                                            ? {
                                                                  ...entry,
                                                                  ...value,
                                                              }
                                                            : entry,
                                                ),
                                            )
                                        }
                                    />
                                </section>
                            ))}
                            <label>
                                Причина изменения
                                {historical
                                    ? ' (обязательно для завершённого обучения)'
                                    : ' (необязательно)'}
                                <textarea
                                    className={styles.field}
                                    rows={2}
                                    maxLength={2000}
                                    required={Boolean(historical && changed)}
                                    disabled={busy}
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                />
                            </label>
                            <div className={styles.actions}>
                                <button
                                    className={styles.primary}
                                    disabled={busy || !changed}
                                >
                                    {busy
                                        ? 'Сохранение…'
                                        : 'Сохранить финансирование'}
                                </button>
                            </div>
                        </form>
                    ) : (
                        <p>В группе нет назначенных слушателей.</p>
                    )}
                </>
            )}
        </div>
    );
}
