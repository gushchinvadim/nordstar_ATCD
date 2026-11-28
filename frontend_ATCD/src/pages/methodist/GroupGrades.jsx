import CompletionDateModal from '../../components/CompletionDateModal';
// src/pages/methodist/GroupGrades.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api/config';
import styles from './GroupGrades.module.css';

const GroupGrades = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    
    const [showCompletion, setShowCompletion] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState('');
    const [groupInfo, setGroupInfo] = useState(null);
    const readOnly = groupInfo?.status === 'cancelled';
    const [instructors, setInstructors] = useState([]);
    const [students, setStudents] = useState([]);
    const [changedCells, setChangedCells] = useState(new Set());

    useEffect(() => {
        fetchData();
    }, [groupId]);

    const fetchData = async () => {
        setLoading(true);
        try {
            const response = await api.get(`/api/docs/groups/${groupId}/grades/`);
            setGroupInfo(response.data.group_info);
            setInstructors(response.data.instructors);
            setStudents(response.data.students);
        } catch (error) {
            console.error("Ошибка загрузки данных:", error);
            alert("Не удалось загрузить журнал оценок");
        } finally {
            setLoading(false);
        }
    };

    const handleCellChange = (enrollmentId, sectionId, field, value) => {
        setSaveMessage('');
        const key = `${enrollmentId}_${sectionId}_${field}`;
        setChangedCells(prev => new Set(prev).add(key));

        setStudents(prevStudents => prevStudents.map(student => {
            if (student.enrollment_id !== enrollmentId) return student;
            
            return {
                ...student,
                assessments: student.assessments.map(assess => {
                    if (assess.section_id !== sectionId) return assess;
                    return { ...assess, [field]: value };
                })
            };
        }));
    };

    const saveGrades = async () => {
        if (saving || changedCells.size === 0) return;

        setSaving(true);
        setSaveMessage('');
        const updates = [];

        students.forEach(student => {
            student.assessments.forEach(assess => {
                const scoreKey = `${student.enrollment_id}_${assess.section_id}_score`;
                const dateKey = `${student.enrollment_id}_${assess.section_id}_date`;
                const instKey = `${student.enrollment_id}_${assess.section_id}_instructor_id`;

                if (changedCells.has(scoreKey) || changedCells.has(dateKey) || changedCells.has(instKey)) {
                    updates.push({
                        enrollment_id: student.enrollment_id,
                        section_id: assess.section_id,
                        score: assess.score,
                        date: assess.date,
                        instructor_id: assess.instructor_id
                    });
                }
            });
        });

        try {
            const response = await api.post(`/api/docs/groups/${groupId}/grades/`, { updates });
            const { saved_count: savedCount, warnings = [] } = response.data;
            if (savedCount !== updates.length || warnings.length > 0) {
                setSaveMessage(warnings.join(' ') || `Сохранено ${savedCount} из ${updates.length}. Проверьте заполнение оценок и повторите сохранение.`);
                return;
            }
            setChangedCells(new Set());
            setSaveMessage(`Оценки сохранены: ${savedCount}.`);
        } catch (error) {
            console.error("Ошибка сохранения:", error);
            setSaveMessage('Не удалось сохранить оценки. Повторите попытку.');
        } finally {
            setSaving(false);
        }
    };

    const completeAllPassed = () => {
        if (changedCells.size) { setSaveMessage('Сначала сохраните изменения оценок.'); return; }
        setShowCompletion(true);
    };

    const dismissFailed = async () => {
        if (changedCells.size) {
            setSaveMessage('Сначала сохраните изменения оценок.');
            return;
        }
        if (!window.confirm('⚠️ Отчислить всех студентов, не сдавших разделы? Это действие необратимо!')) {
            return;
        }

        try {
            const response = await api.post(`/api/docs/groups/${groupId}/dismiss-failed/`);
            alert(`✅ ${response.data.message}`);
            fetchData();
        } catch (error) {
            console.error("Ошибка:", error);
            alert(error.response?.data?.error || 'Ошибка при отчислении');
        }
    };

    if (loading) return <div className={styles.loading}>Загрузка журнала...</div>;
    
    if (!groupInfo) {
        return (
            <div className={styles.container}>
                <div className={styles.error}>
                    <h2>❌ Не удалось загрузить журнал оценок</h2>
                    <button className={styles.backBtn} onClick={() => navigate('/groups')}>← Назад</button>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <button className={styles.backBtn} onClick={() => navigate('/groups')}>← Назад к группам</button>
                <h1>Журнал оценок: {groupInfo.assigned_number}</h1>
                <p>{groupInfo.module_code} — {groupInfo.module_title}</p>
            </div>

            {showCompletion && <CompletionDateModal group={{ id: groupId, assigned_number: groupInfo.assigned_number }} studentsOnly onClose={() => setShowCompletion(false)} onCompleted={(data) => { setShowCompletion(false); setSaveMessage(data.message); fetchData(); }} />}
            {readOnly && <p role="status">Группа отменена. Журнал доступен только для просмотра.</p>}
            {/* ПАНЕЛЬ МАССОВЫХ ДЕЙСТВИЙ */}
            <div className={styles.massActions}>
                <button 
                    className={`${styles.massBtn} ${styles.saveBtn} ${changedCells.size > 0 ? styles.hasChanges : ''}`} 
                    onClick={saveGrades}
                    disabled={readOnly || saving || changedCells.size === 0}
                >
                     {saving ? 'Сохранение...' : `Сохранить оценки (${changedCells.size})`}
                </button>
                
                <button 
                    className={`${styles.massBtn} ${styles.completeBtn}`} 
                    onClick={completeAllPassed}
                    disabled={readOnly || saving}
                >
                    ✓ Завершить всех сдавших
                </button>
                
                <button 
                    className={`${styles.massBtn} ${styles.dismissBtn}`} 
                    onClick={dismissFailed}
                    disabled={readOnly || saving}
                >
                    ⚠ Отчислить не сдавших
                </button>
            </div>

            <p role="status" className={styles.saveMessage}>{saveMessage}</p>

            <div className={styles.tableWrapper} role="region" aria-label="Таблица оценок группы" tabIndex={0}>
                <table role="table" className={styles.gradesTable}>
                    <thead role="rowgroup">
                        <tr role="row">
                            <th role="columnheader" className={styles.stickyCol1}>№</th>
                            <th role="columnheader" className={styles.stickyCol2}>ФИО студента</th>
                            <th role="columnheader" className={styles.stickyCol3}>Статус</th>
                            {students.length > 0 && students[0].assessments && students[0].assessments.map(assess => (
                                <th role="columnheader" key={assess.section_id} className={styles.sectionHeader} title={assess.section_title}>
                                    {assess.section_title.length > 30 ? assess.section_title.substring(0, 30) + '...' : assess.section_title}
                                </th>
                            ))}
                        </tr>
                    </thead>

                    <tbody role="rowgroup">
                        {students
                            .map(student => (
                                <tr role="row" key={student.enrollment_id} className={styles[`status${student.status}`]}>
                                    <td role="cell" data-label="№" className={styles.stickyCol1}>{student.number_in_group}</td>
                                    <td role="cell" data-label="Слушатель" data-wide="" className={`${styles.stickyCol2} ${styles.studentName}`}>{student.student_name}</td>
                                    <td role="cell" data-label="Статус" className={styles.stickyCol3}>{student.status_display}</td>
                                    
                                    {student.assessments && student.assessments.map(assess => {
                                        const isChanged = changedCells.has(`${student.enrollment_id}_${assess.section_id}_score`) ||
                                                        changedCells.has(`${student.enrollment_id}_${assess.section_id}_date`);
                                        
                                        return (
                                            <td role="cell" data-label={assess.section_title} data-wide="" key={assess.section_id} className={`${styles.assessmentCell} ${isChanged ? styles.changed : ''}`}>
                                                {assess.grade_type === 'binary' || assess.grade_type === 'pass_fail' ? (
                                                    <select 
                                                        disabled={readOnly || saving || student.status === 'dismissed'}
                                                        aria-label={`Оценка: ${assess.section_title}`} value={assess.score ?? ''} 
                                                        onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'score', e.target.value === '' ? null : parseInt(e.target.value))}
                                                        className={styles.inputSelect}
                                                    >
                                                        <option value="">—</option>
                                                        <option value="1">✓ Зачтено</option>
                                                        <option value="0">Не зачтено</option>
                                                    </select>
                                                ) : (
                                                    <input 
                                                        type="number" 
                                                        min="0" max="5" 
                                                        disabled={readOnly || saving || student.status === 'dismissed'}
                                                        aria-label={`Оценка: ${assess.section_title}`} value={assess.score ?? ''} 
                                                        onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'score', e.target.value === '' ? null : parseInt(e.target.value))}
                                                        className={styles.inputNumber}
                                                        placeholder="—"
                                                    />
                                                )}
                                                
                                                <input 
                                                    type="date" 
                                                    disabled={readOnly || saving || student.status === 'dismissed'}
                                                    aria-label={`Дата: ${assess.section_title}`} value={assess.date || ''} 
                                                    onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'date', e.target.value)}
                                                    className={styles.inputDate}
                                                />
                                                
                                                <select 
                                                    disabled={readOnly || saving || student.status === 'dismissed'}
                                                    value={assess.instructor_id || ''} 
                                                    onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'instructor_id', e.target.value === '' ? null : parseInt(e.target.value))}
                                                    className={styles.inputSelectSmall}
                                                    aria-label={`Преподаватель: ${assess.section_title}`}
                                                >
                                                    <option value="">— преп. —</option>
                                                    {instructors.map(inst => (
                                                        <option key={inst.id} value={inst.id}>{inst.name}</option>
                                                    ))}
                                                </select>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default GroupGrades;