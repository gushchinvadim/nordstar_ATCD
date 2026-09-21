// src/pages/instructor/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import styles from './Dashboard.module.css';
import api from '../../api/config';

const InstructorDashboard = () => {
    const [groups, setGroups] = useState([]);
    const [expandedGroup, setExpandedGroup] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [savingGrades, setSavingGrades] = useState({});
    const [tempGrades, setTempGrades] = useState({});
    
    // Состояние для баннера ошибок валидации
    const [completionError, setCompletionError] = useState(null);

    useEffect(() => {
        fetchGroups();
    }, []);

    const fetchGroups = async () => {
        try {
            const response = await api.get('/api/execution/instructor/groups/');
            setGroups(response.data);
            setLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки групп:", err);
            setError('Ошибка загрузки данных');
            setLoading(false);
        }
    };

    const handleConfirm = async (actionType, params = {}) => {
        try {
            if (actionType === 'lesson_completed') {
                await api.post(`/api/execution/instructor/schedule/${params.schedule_item_id}/log/`, { action_type: actionType });
            } else {
                await api.post('/api/execution/instructor/log/', { action_type: actionType, ...params });
            }
            await fetchGroups();
            alert('✅ Действие успешно подтверждено!');
        } catch (err) {
            console.error("Ошибка подтверждения:", err);
            alert(err.response?.data?.error || 'Ошибка подтверждения.');
        }
    };

    const handleSaveFinalGrades = async (groupId, studentsWithGrades) => {
        const gradesPayload = studentsWithGrades
            .filter(s => s.temp_final_score !== undefined && s.temp_final_score !== null && String(s.temp_final_score).trim() !== '')
            .map(s => ({
                enrollment_id: s.enrollment_id,
                section_id: s.final_section_id,
                score: Number(s.temp_final_score),
                notes: s.temp_final_notes || ''
            }));

        if (gradesPayload.length === 0) {
            alert("⚠️ Нет оценок для сохранения. Введите хотя бы одну.");
            return;
        }

        setSavingGrades(prev => ({ ...prev, [groupId]: true }));
        try {
            await api.post('/api/execution/instructor/grades/', {
                group_id: Number(groupId),
                grades: gradesPayload
            });
            alert('Итоговые оценки сохранены!');
            await fetchGroups();
        } catch (err) {
            console.error("Ошибка сохранения:", err);
            alert(err.response?.data?.error || 'Ошибка сохранения.');
        } finally {
            setSavingGrades(prev => ({ ...prev, [groupId]: false }));
        }
    };

    // === НОВАЯ ЛОГИКА: Завершение группы с валидацией ===
    const handleCompleteGroup = async (groupId) => {
        setCompletionError(null); // Сброс предыдущих ошибок
        try {
            const response = await api.post(`/api/execution/instructor/groups/${groupId}/complete/`);
            alert(response.data.message);
            
            // Мгновенно удаляем группу из интерфейса, так как она теперь 'completed'
            setGroups(prev => prev.filter(g => g.group_id !== groupId));
        } catch (err) {
            if (err.response?.status === 400 && err.response?.data?.missing_items) {
                // Показываем красивый баннер со списком проблем
                setCompletionError({
                    groupId,
                    items: err.response.data.missing_items
                });
            } else {
                alert(err.response?.data?.error || 'Ошибка при завершении группы');
            }
        }
    };

    const closeErrorBanner = () => {
        setCompletionError(null);
    };

    const toggleGroup = (groupId) => {
        setExpandedGroup(expandedGroup === groupId ? null : groupId);
    };

    const updateTempGrade = (enrollmentId, field, value) => {
        setTempGrades(prev => ({
            ...prev,
            [enrollmentId]: { ...prev[enrollmentId], [field]: value }
        }));
    };

    if (loading) return <div className={styles.loading}>Загрузка...</div>;
    if (error) return <div className={styles.error}>{error}</div>;

    return (
        <div className={styles.container}>
            <h1 className={styles.mainTitle}>Кабинет преподавателя</h1>
            <h2 className={styles.subtitle}>Мои активные группы</h2>
            
            {groups.length === 0 ? (
                <div className={styles.emptyState}>
                    <p>🎉 У вас нет активных групп. Все занятия проведены и группы переданы методисту!</p>
                </div>
            ) : (
                groups.map(group => (
                    <div key={group.group_id} className={styles.moduleCard}>
                        <div className={styles.moduleHeader} onClick={() => toggleGroup(group.group_id)}>
                            <div className={styles.moduleInfo}>
                                <h3>{group.module_title}</h3>
                                <span className={styles.moduleCode}>Группа: {group.group_number}</span>
                            </div>
                            <button className={styles.expandButton}>
                                {expandedGroup === group.group_id ? '▲ Свернуть' : '▼ Открыть управление группой'}
                            </button>
                        </div>

                        {expandedGroup === group.group_id && (
                            <div className={styles.signaturesBlock}>
                                
                                {/* 1. Расписание */}
                                <div className={styles.signatureSection}>
                                    <h4>1. Ознакомление с учебным расписанием</h4>
                                    <a href={group.schedule_doc.url} target="_blank" rel="noopener noreferrer" className={styles.docLink}>
                                        📄 Открыть документ с расписанием
                                    </a>
                                    {group.schedule_doc.has_ack ? (
                                        <div className={styles.confirmed}>
                                            ✅ Ознакомлен {new Date(group.schedule_doc.ack_date).toLocaleString('ru-RU')}
                                        </div>
                                    ) : (
                                        <button className={styles.actionButton} onClick={() => handleConfirm('instructor_schedule_ack', { group_id: group.group_id })}>
                                            Ознакомление с расписанием
                                        </button>
                                    )}
                                </div>

                                {/* 2. Инструктаж (Теперь с групповым статусом) */}
                                <div className={styles.signatureSection}>
                                    <h4>2. Инструктаж по ОТ, ТБ, ППБ</h4>
                                    {group.group_has_safety_ack ? (
                                        <div className={styles.infoBannerOk}>
                                            ✅ Инструктаж проведен (методистом или преподавателем). Слушатели ознакомились.
                                        </div>
                                    ) : (
                                        <div className={styles.infoBannerWarn}>
                                            ⏳ Инструктаж еще не проведен. Обратитесь к методисту или проведите его.
                                        </div>
                                    )}
                                    <div className={styles.studentList}>
                                        {group.students.map(student => (
                                            <div key={student.enrollment_id} className={styles.studentRow}>
                                                <span className={styles.studentName}>{student.number}. {student.student_name}</span>
                                                {student.briefing_done ? (
                                                    <span className={styles.confirmedSmall}>✅ {new Date(student.briefing_date).toLocaleDateString()}</span>
                                                ) : (
                                                    <button className={styles.smallButton} onClick={() => handleConfirm('instructor_briefing_done', { enrollment_id: student.enrollment_id })}>
                                                        Провести инструктаж
                                                    </button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* 3. Занятия */}
                                <div className={styles.signatureSection}>
                                    <h4>3. Отметка о проведении занятий</h4>
                                    {group.classes.length === 0 ? (
                                        <p className={styles.pending}>Нет занятий</p>
                                    ) : (
                                        <div className={styles.attendanceList}>
                                            {group.classes.map(cls => (
                                                <div key={cls.id} className={styles.attendanceItem}>
                                                    <div className={styles.attendanceInfo}>
                                                        <span className={styles.date}>{cls.date}</span>
                                                        <span className={styles.time}>{cls.time}</span>
                                                        <span className={styles.section}>{cls.section_title}</span>
                                                    </div>
                                                    {cls.is_completed ? (
                                                        <span className={styles.confirmedSmall}>✅ {cls.completion_signature}</span>
                                                    ) : (
                                                        <button className={styles.smallButton} onClick={() => handleConfirm('lesson_completed', { schedule_item_id: cls.id })}>
                                                            Подтвердить проведение
                                                        </button>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* 4. Промежуточные оценки */}
                                <div className={styles.signatureSection}>
                                    <h4>4. Промежуточные оценки (для допуска)</h4>
                                    <div className={styles.studentList}>
                                        {group.students.map(student => (
                                            <div key={student.enrollment_id} className={styles.studentRow}>
                                                <span className={styles.studentName}>{student.number}. {student.student_name}</span>
                                                <div className={styles.gradesPreview}>
                                                    {student.intermediate_grades.length > 0 ? (
                                                        student.intermediate_grades.map((g, idx) => (
                                                            <span key={idx} className={styles.gradeBadge}>
                                                                {g.section_title}: <b>{g.score !== null ? g.score : '—'}</b>
                                                            </span>
                                                        ))
                                                    ) : (
                                                        <span className={styles.pendingText}>Нет оценок</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* 5. Итоговая аттестация */}
                                <div className={styles.signatureSection}>
                                    <h4>5. Итоговая аттестация (экзамен)</h4>
                                    <div className={styles.studentList}>
                                        {group.students.map(student => {
                                            if (!student.final_section_id) return null;
                                            const currentTemp = tempGrades[student.enrollment_id] || {};
                                            const displayScore = currentTemp.score !== undefined ? currentTemp.score : student.final_score;
                                            
                                            return (
                                                <div key={student.enrollment_id} className={styles.studentRowGrade}>
                                                    <span className={styles.studentName}>{student.number}. {student.student_name}</span>
                                                    <div className={styles.gradeInputWrapper}>
                                                        <input 
                                                            type="number"
                                                            min={student.final_grade_type === 'binary' ? '0' : '2'}
                                                            max={student.final_grade_type === 'binary' ? '1' : '5'}
                                                            placeholder={student.final_grade_type === 'binary' ? '0/1' : '2-5'}
                                                            value={displayScore ?? ''}
                                                            onChange={(e) => updateTempGrade(student.enrollment_id, 'score', e.target.value)}
                                                            className={styles.scoreInput}
                                                        />
                                                        <input 
                                                            type="text"
                                                            placeholder="Комментарий"
                                                            value={currentTemp.notes || ''}
                                                            onChange={(e) => updateTempGrade(student.enrollment_id, 'notes', e.target.value)}
                                                            className={styles.notesInput}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                    
                                    {(() => {
                                        const studentsWithFinalSection = group.students.filter(s => s.final_section_id).length;
                                        const studentsWithScore = group.students.filter(s => s.final_section_id && s.final_score !== null).length;
                                        const hasNewGrades = group.students.some(s => s.final_section_id && tempGrades[s.enrollment_id]?.score !== undefined);
                                        
                                        let buttonClass = styles.saveButton;
                                        let buttonText = '💾 Сохранить итоговые оценки';
                                        
                                        if (studentsWithFinalSection === 0) {
                                            buttonClass = `${styles.saveButton} ${styles.saveButtonDisabled}`;
                                            buttonText = 'Итоговая аттестация не предусмотрена';
                                        } else if (studentsWithScore === studentsWithFinalSection) {
                                            buttonClass = `${styles.saveButton} ${styles.saveButtonComplete}`;
                                            buttonText = `✅ Все оценки сохранены (${studentsWithScore}/${studentsWithFinalSection})`;
                                        } else if (studentsWithScore > 0) {
                                            buttonClass = `${styles.saveButton} ${styles.saveButtonPartial}`;
                                            buttonText = `💾 Сохранить оценки (${studentsWithScore}/${studentsWithFinalSection} выставлено)`;
                                        } else if (!hasNewGrades) {
                                            buttonClass = `${styles.saveButton} ${styles.saveButtonInactive}`;
                                            buttonText = 'Введите оценки для сохранения';
                                        }
                                        
                                        return (
                                            <button 
                                                className={buttonClass}
                                                onClick={() => {
                                                    const studentsToUpdate = group.students
                                                        .filter(s => s.final_section_id && (tempGrades[s.enrollment_id]?.score !== undefined))
                                                        .map(s => ({
                                                            ...s,
                                                            temp_final_score: tempGrades[s.enrollment_id].score,
                                                            temp_final_notes: tempGrades[s.enrollment_id].notes
                                                        }));
                                                    handleSaveFinalGrades(group.group_id, studentsToUpdate);
                                                }}
                                                disabled={savingGrades[group.group_id] || studentsWithFinalSection === 0}
                                            >
                                                {savingGrades[group.group_id] ? 'Сохранение...' : buttonText}
                                            </button>
                                        );
                                    })()}
                                </div>

                                {/* 6. ЗАВЕРШЕНИЕ ГРУППЫ */}
                                <div className={styles.signatureSection} style={{ borderTop: '2px solid #e0e0e0', marginTop: '20px', paddingTop: '20px' }}>
                                    <h4>6. Завершение работы с группой</h4>
                                    <p className={styles.hintText}>
                                        Нажмите эту кнопку, когда все занятия проведены, инструктажи сделаны и оценки выставлены. 
                                        Группа исчезнет из вашего списка и будет передана методисту для архивации.
                                    </p>
                                    
                                    <button className={styles.btnCompleteGroup} onClick={() => handleCompleteGroup(group.group_id)}>
                                        ✅ Завершить всех сдавших и передать методисту
                                    </button>

                                    {/* ВСПЛЫВАЮЩИЙ БАННЕР ОШИБОК ВАЛИДАЦИИ */}
                                    {completionError && completionError.groupId === group.group_id && (
                                        <div className={styles.errorBanner}>
                                            <div className={styles.errorBannerHeader}>
                                                <span>⚠️ Невозможно завершить группу</span>
                                                <button onClick={closeErrorBanner} className={styles.closeBtn}>×</button>
                                            </div>
                                            <ul className={styles.errorList}>
                                                {completionError.items.map((item, idx) => (
                                                    <li key={idx}>{item}</li>
                                                ))}
                                            </ul>
                                            <p className={styles.errorHint}>
                                                Пожалуйста, устраните эти замечания или обратитесь к методисту.
                                            </p>
                                        </div>
                                    )}
                                </div>

                            </div>
                        )}
                    </div>
                ))
            )}
        </div>
    );
};

export default InstructorDashboard;