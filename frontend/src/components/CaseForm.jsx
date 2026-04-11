import React, { useState } from 'react'
import styles from './CaseForm.module.css'

const COMMON_CHARGES = [
    'IPC 302 - Murder',
    'IPC 376 - Rape',
    'IPC 379 - Theft',
    'IPC 380 - Theft in dwelling house',
    'IPC 392 - Robbery',
    'IPC 395 - Dacoity',
    'IPC 406 - Criminal breach of trust',
    'IPC 420 - Cheating',
    'IPC 411 - Receiving stolen property',
    'IPC 465 - Forgery',
    'NDPS Act',
    'PMLA',
    'SC/ST Act',
]

const STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
    'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
    'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
    'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
    'Delhi', 'Jammu & Kashmir',
]

const DEFAULTS = {
    case_id: '',
    accused_name: '',
    fir_text: '',
    charges: [],
    detention_days: '',
    court: '',
    state: 'Maharashtra',
    custom_charge: '',
}

export default function CaseForm({ onSubmit, loading }) {
    const [form, setForm] = useState(DEFAULTS)
    const [errors, setErrors] = useState({})

    const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

    const toggleCharge = (charge) => {
        set('charges', form.charges.includes(charge)
            ? form.charges.filter((item) => item !== charge)
            : [...form.charges, charge])
    }

    const addCustomCharge = () => {
        const charge = form.custom_charge.trim()
        if (charge && !form.charges.includes(charge)) {
            set('charges', [...form.charges, charge])
            set('custom_charge', '')
        }
    }

    const validate = () => {
        const nextErrors = {}
        if (!form.accused_name.trim()) nextErrors.accused_name = 'Required'
        if (!form.fir_text.trim()) nextErrors.fir_text = 'Required'
        if (form.charges.length === 0) nextErrors.charges = 'Select at least one charge'
        if (!form.detention_days || isNaN(form.detention_days) || +form.detention_days < 1) {
            nextErrors.detention_days = 'Enter a valid number'
        }
        if (!form.court.trim()) nextErrors.court = 'Required'
        if (!form.state) nextErrors.state = 'Required'
        setErrors(nextErrors)
        return Object.keys(nextErrors).length === 0
    }

    const handleSubmit = (event) => {
        event.preventDefault()
        if (!validate()) return

        onSubmit({
            case_id: form.case_id.trim() || `CASE-${Date.now()}`,
            accused_name: form.accused_name.trim(),
            fir_text: form.fir_text.trim(),
            charges: form.charges,
            detention_days: parseInt(form.detention_days, 10),
            court: form.court.trim(),
            state: form.state,
        })
    }

    const isValid = form.accused_name && form.fir_text && form.charges.length > 0
        && form.detention_days && form.court && form.state

    return (
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
            <div className={styles.section}>
                <div className={styles.sectionLabel}>
                    <span className={styles.sectionNum}>01</span>
                    Accused Details
                </div>
                <div className={styles.fields}>
                    <Field label="Full Name" required error={errors.accused_name}>
                        <input
                            type="text"
                            placeholder="e.g. Ramesh Shinde"
                            value={form.accused_name}
                            onChange={(event) => set('accused_name', event.target.value)}
                            className={errors.accused_name ? styles.inputError : ''}
                        />
                    </Field>
                    <Field label="Case / FIR Reference">
                        <input
                            type="text"
                            placeholder="e.g. FIR-2026-001 (auto-generated if blank)"
                            value={form.case_id}
                            onChange={(event) => set('case_id', event.target.value)}
                        />
                    </Field>
                </div>
            </div>

            <div className={styles.section}>
                <div className={styles.sectionLabel}>
                    <span className={styles.sectionNum}>02</span>
                    FIR &amp; Allegations
                </div>
                <Field label="FIR Text / Case Summary" required error={errors.fir_text}>
                    <textarea
                        rows={5}
                        placeholder="Describe the alleged incident, circumstances of arrest, and any known facts. Include what was recovered, witness statements mentioned in the FIR, and any co-accused."
                        value={form.fir_text}
                        onChange={(event) => set('fir_text', event.target.value)}
                        className={errors.fir_text ? styles.inputError : ''}
                    />
                </Field>
            </div>

            <div className={styles.section}>
                <div className={styles.sectionLabel}>
                    <span className={styles.sectionNum}>03</span>
                    Sections Charged
                </div>
                {errors.charges && <div className={styles.error}>{errors.charges}</div>}
                <div className={styles.chargeGrid}>
                    {COMMON_CHARGES.map((charge) => (
                        <button
                            type="button"
                            key={charge}
                            className={`${styles.chargeTag} ${form.charges.includes(charge) ? styles.chargeTagActive : ''}`}
                            onClick={() => toggleCharge(charge)}
                        >
                            {charge}
                        </button>
                    ))}
                </div>
                <div className={styles.customCharge}>
                    <input
                        type="text"
                        placeholder="Add custom section (e.g. IPC 307 - Attempt to murder)"
                        value={form.custom_charge}
                        onChange={(event) => set('custom_charge', event.target.value)}
                        onKeyDown={(event) => event.key === 'Enter' && (event.preventDefault(), addCustomCharge())}
                    />
                    <button type="button" className={styles.addBtn} onClick={addCustomCharge}>
                        Add
                    </button>
                </div>
                {form.charges.length > 0 && (
                    <div className={styles.selectedCharges}>
                        {form.charges.map((charge) => (
                            <span key={charge} className={styles.selectedTag}>
                                {charge}
                                <button type="button" onClick={() => toggleCharge(charge)} aria-label={`Remove ${charge}`}>
                                    ×
                                </button>
                            </span>
                        ))}
                    </div>
                )}
            </div>

            <div className={styles.section}>
                <div className={styles.sectionLabel}>
                    <span className={styles.sectionNum}>04</span>
                    Detention &amp; Court
                </div>
                <div className={styles.fields}>
                    <Field label="Days in Custody" required error={errors.detention_days}>
                        <div className={styles.daysInput}>
                            <input
                                type="number"
                                min="1"
                                max="9999"
                                placeholder="e.g. 248"
                                value={form.detention_days}
                                onChange={(event) => set('detention_days', event.target.value)}
                                className={errors.detention_days ? styles.inputError : ''}
                            />
                            {form.detention_days && !isNaN(form.detention_days) && (
                                <span className={styles.daysHint}>
                                    {(form.detention_days / 30).toFixed(1)} months
                                </span>
                            )}
                        </div>
                    </Field>
                    <Field label="Presiding Court" required error={errors.court}>
                        <input
                            type="text"
                            placeholder="e.g. Sessions Court, Pune"
                            value={form.court}
                            onChange={(event) => set('court', event.target.value)}
                            className={errors.court ? styles.inputError : ''}
                        />
                    </Field>
                    <Field label="State" required error={errors.state}>
                        <select value={form.state} onChange={(event) => set('state', event.target.value)}>
                            {STATES.map((state) => <option key={state}>{state}</option>)}
                        </select>
                    </Field>
                </div>
            </div>

            <div className={styles.submitRow}>
                <button
                    type="submit"
                    className={styles.submitBtn}
                    disabled={loading || !isValid}
                >
                    {loading ? (
                        <>
                            <span className={styles.spinner} />
                            Analysing case...
                        </>
                    ) : (
                        <>
                            <span className={styles.submitIcon}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                                    <path d="M12 3v18" />
                                    <path d="M5 7h14" />
                                    <path d="M7.5 7 4 13a3.5 3.5 0 0 0 7 0L7.5 7Z" />
                                    <path d="m16.5 7-3.5 6a3.5 3.5 0 0 0 7 0l-3.5-6Z" />
                                    <path d="M9 21h6" />
                                </svg>
                            </span>
                            Generate Legal Brief
                        </>
                    )}
                </button>
                {loading && (
                    <div className={styles.loadingNote}>
                        Running eligibility, rights &amp; advocate agents - this takes 30-60 seconds.
                    </div>
                )}
            </div>
        </form>
    )
}

function Field({ label, required, error, children }) {
    return (
        <div className={`${styles.field} ${error ? styles.fieldError : ''}`}>
            <label className={styles.label}>
                {label}
                {required && <span className={styles.req} aria-hidden>*</span>}
            </label>
            {children}
            {error && <div className={styles.error}>{error}</div>}
        </div>
    )
}
