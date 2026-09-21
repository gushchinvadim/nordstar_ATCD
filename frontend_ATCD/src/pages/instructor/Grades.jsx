// src/pages/instructor/Grades.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api/config'; // <-- Используем ваш настроенный api
import styles from './Grades.module.css';

const InstructorGrades = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [students, setStudents] = useState([]);
    const [editableSections, setEditableSections] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchGrades();
    }, [groupId]);

    const fetchGrades = async () => {
        try {
            // Запрашиваем оценки для конкретной группы
            const response = await api.get(`/api/instructor/grades/${groupId}/`);
            setStudents(response.data);
            
            // Собираем уникальные ID разделов, которые можно редактировать
            if (response.data.length > 0 && response.data[0].editable_sections) {
                setEditableSections(response.data[0].editable_sections);
            }
            setLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки оценок:", err);
            alert('Ошибка загрузки данных. Проверьте консоль.');
            setLoading(false);
        }
    };

    const handleScoreChange = (enrollmentId, sectionId, score) => {
        setStudents(prev => prev.map(student => {
            if (student.id !== enrollmentId) return student;
            
            const assessments = [...student.assessments];
            const existingIndex = assessments.findIndex(a => a.section === sectionId);
            
            if (existingIndex >= 0) {
                assessments[existingIndex] = { ...assessments[existingIndex], score: score === '' ? null : parseInt(score, 10) };
            } else {
                assessments.push({ section: sectionId, score: score === '' ? null : parseInt(score, 10), passed: false });
            }
            return { ...student, assessments };
        }));
    };

    const handleNotesChange = (enrollmentId, sectionId, notes) => {
        setStudents(prev => prev.map(student => {
            if (student.id !== enrollmentId) return student;
            
            const assessments = [...student.assessments];
            const existingIndex = assessments.findIndex(a => a.section === sectionId);
            
            if (existingIndex >= 0) {
                assessments[existingIndex] = { ...assessments[existingIndex], notes };
            } else {
                assessments.push({ section: sectionId, score: null, notes });
            }
            return { ...student, assessments };
        }));
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const gradesPayload = [];
            students.forEach(student => {
                student.assessments.forEach(assessment => {
                    // Отправляем только те оценки, которые были изменены или относятся к редактируемым разделам
                    if (editableSections.includes(assessment.section) && assessment.score !== null && assessment.score !== '') {
                        gradesPayload.push({
                            enrollment_id: student.id,
                            section_id: assessment.section,
                            score: assessment.score,
                            notes: assessment.notes || ''
                        });
                    }
                });
            });

            // Отправляем на бэкенд. 
            // ВАЖНО: На бэкенде в views.py при сохранении Assessment сработает метод save(), 
            // который автоматически вызовет self.enrollment.calculate_total_hours() и обновит статусы!
            await api.post('/api/instructor/grades/', {
                group_id: parseInt(groupId),
                grades: gradesPayload
            });

            alert('Оценки успешно сохранены! Статусы и часы пересчитаны.');
            navigate('/instructor/dashboard'); // Возвращаемся в расписание
        } catch (err) {
            console.error("Ошибка сохранения:", err);
            alert('Ошибка сохранения оценок. Проверьте консоль.');
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <div className={styles.loading}>Загрузка журнала оценок...</div>;

    return (
        <div className={styles.container}>
            <button className={styles.backButton} onClick={() => navigate('/instructor/dashboard')}>
                ← Назад к расписанию
            </button>

            <h1 className={styles.title}>Журнал оценок группы</h1>

            <div className={styles.tableWrapper}>
                <table className={styles.gradesTable}>
                    <thead>
                        <tr>
                            <th>№</th>
                            <th>ФИО слушателя</th>
                            {editableSections.map(sectionId => (
                                <th key={sectionId}>Раздел {sectionId}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {students.map(student => (
                            <tr key={student.id}>
                                <td>{student.number_in_group}</td>
                                <td>{student.student_name}</td>
                                {editableSections.map(sectionId => {
                                    const assessment = student.assessments.find(a => a.section === sectionId);
                                    // Если оценка уже есть в БД, показываем её, иначе пусто
                                    const score = assessment?.score ?? ''; 
                                    const notes = assessment?.notes || '';
                                    const isPassed = assessment?.passed;
                                    
                                    return (
                                        <td key={sectionId} className={styles.editableCell}>
                                            <input
                                                type="number"
                                                value={score}
                                                onChange={(e) => handleScoreChange(student.id, sectionId, e.target.value)}
                                                className={`${styles.scoreInput} ${isPassed ? styles.passed : ''}`}
                                                min="2"
                                                max="5"
                                                placeholder="-"
                                            />
                                            <input
                                                type="text"
                                                value={notes}
                                                onChange={(e) => handleNotesChange(student.id, sectionId, e.target.value)}
                                                className={styles.notesInput}
                                                placeholder="Комментарий"
                                            />
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <button 
                className={styles.saveButton}
                onClick={handleSave}
                disabled={saving}
            >
                {saving ? 'Сохранение и пересчет...' : '💾 Сохранить оценки и завершить этапы'}
            </button>
        </div>
    );
};

export default InstructorGrades;