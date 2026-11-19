import { useEffect, useRef, useState } from 'react';
import api from '../api/config';
import styles from './CompletionDateModal.module.css';

export default function CancelGroupModal({ group, onClose, onCancelled }) {
    const dialog = useRef(null);
    const [context, setContext] = useState(null);
    const [date, setDate] = useState('');
    const [reason, setReason] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        dialog.current.showModal();
        let active = true;
        api.get(`/api/execution/methodist/groups/${group.id}/cancel/`)
            .then(({ data }) => { if (active) { setContext(data); setDate(data.cancellation_date); } })
            .catch(() => { if (active) setError('Не удалось получить дату группы. Закройте окно и повторите попытку.'); });
        return () => { active = false; };
    }, [group.id]);
    async function submit(event) {
        event.preventDefault();
        if (busy) return;
        setBusy(true); setError('');
        try {
            await api.post(`/api/execution/methodist/groups/${group.id}/cancel/`, { cancellation_date: date, cancellation_reason: reason.trim() });
            onCancelled();
        } catch (err) {
            const data = err.response?.data;
            setError(data?.error || Object.values(data || {}).flat().join(' ') || 'Не удалось отменить группу. Повторите попытку.');
        } finally { setBusy(false); }
    }
    return <dialog ref={dialog} className={styles.dialog} aria-labelledby="cancel-group-title" onCancel={(e) => { e.preventDefault(); if (!busy) onClose(); }}>
        <form onSubmit={submit}>
            <h2 id="cancel-group-title">Отменить группу</h2>
            <p>{group.assigned_number}</p>
            <p>Группа уйдёт из активных занятий. Назначения, оценки, ПЭП и документы сохранятся. Продолжить обучение в отменённой группе будет нельзя.</p>
            {context && <>
                <label>Фактическая дата отмены<input autoFocus type="date" required max={context.maximum_date} value={date} disabled={busy} onChange={(e) => setDate(e.target.value)} /></label>
                <p className={styles.hint}>Местное время группы: {context.timezone}. Автор и время фиксации отмены сохраняются отдельно.</p>
                <label>Причина отмены<textarea required maxLength={2000} rows={4} value={reason} disabled={busy} onChange={(e) => setReason(e.target.value)} /></label>
            </>}
            {!context && !error && <p role="status">Загрузка…</p>}
            {error && <p role="alert" className={styles.error}>{error}</p>}
            <div className={styles.actions}>
                <button type="button" disabled={busy} onClick={onClose}>Назад</button>
                <button type="submit" disabled={busy || !context || !date || !reason.trim()}>{busy ? 'Сохранение…' : 'Подтвердить отмену группы'}</button>
            </div>
        </form>
    </dialog>;
}
