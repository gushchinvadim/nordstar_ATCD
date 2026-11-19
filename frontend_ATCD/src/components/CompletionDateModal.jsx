import { useEffect, useRef, useState } from 'react';
import api from '../api/config';
import styles from './CompletionDateModal.module.css';

export default function CompletionDateModal({ group, studentsOnly = false, onClose, onCompleted }) {
    const dialog = useRef(null);
    const [context, setContext] = useState(null);
    const [date, setDate] = useState('');
    const [reason, setReason] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        dialog.current.showModal();
        let active = true;
        api.get(`/api/execution/methodist/groups/${group.id}/complete/`)
            .then(({ data }) => { if (active) { setContext(data); setDate(data.completion_date); setReason(data.completion_reason || ''); } })
            .catch(() => { if (active) setError('Не удалось получить даты группы. Закройте окно и повторите попытку.'); });
        return () => { active = false; };
    }, [group.id]);
    const needsReason = context && date !== (context.planned_date || context.completion_date) && !context.closed;
    async function submit(event) {
        event.preventDefault();
        if (busy) return;
        setBusy(true); setError('');
        try {
            const url = studentsOnly ? `/api/docs/groups/${group.id}/complete-all/` : `/api/execution/methodist/groups/${group.id}/complete/`;
            const { data } = await api.post(url, { completion_date: date, completion_reason: reason });
            onCompleted(data);
        } catch (err) {
            const data = err.response?.data;
            setError([data?.error, ...(data?.missing_items || [])].filter(Boolean).join(' ') || 'Не удалось завершить операцию. Проверьте дату и повторите попытку.');
        } finally { setBusy(false); }
    }
    return <dialog ref={dialog} className={styles.dialog} aria-labelledby="completion-title" onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
        <form onSubmit={submit}>
            <h2 id="completion-title">{studentsOnly ? 'Завершение обучения слушателей' : 'Завершение группы'}</h2>
            <p>{group.assigned_number}</p>
            {context ? <>
                <p>Дата окончания по расписанию: <strong>{context.planned_date || 'не указана'}</strong></p>
                <label>Фактическая дата окончания
                    <input autoFocus type="date" required value={date || ''} min={context.minimum_date} max={context.maximum_date} disabled={busy || context.closed} onChange={(e) => setDate(e.target.value)} />
                </label>
                <p className={styles.hint}>Местное время группы: {context.timezone}. Время подтверждения и дата выдачи документов фиксируются отдельно.</p>
                {needsReason && <label>Причина изменения даты
                    <textarea required rows="3" value={reason} disabled={busy} onChange={(e) => setReason(e.target.value)} />
                </label>}
                {context.closed && <p>Дата ранее закрытой группы не изменяется. Будет подтверждена только выдача документов.</p>}
            </> : !error && <p role="status">Загрузка дат…</p>}
            {error && <p role="alert" className={styles.error}>{error}</p>}
            <div className={styles.actions}>
                <button type="button" disabled={busy} onClick={onClose}>Отмена</button>
                <button type="submit" disabled={busy || !context || !date || (needsReason && !reason.trim())}>{busy ? 'Сохранение…' : 'Подтвердить завершение'}</button>
            </div>
        </form>
    </dialog>;
}
