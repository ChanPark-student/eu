import { useState } from 'react';
import { ShieldCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';
import api from '../api/client';

function Verify() {
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const [systemName, setSystemName] = useState('');
    const [description, setDescription] = useState('');

    const handleVerify = async () => {
        if (!description.trim()) {
            alert('고객 문서 텍스트를 입력해 주세요.');
            return;
        }

        setIsAnalyzing(true);
        try {
            const userQuestion = systemName.trim() || description.trim().slice(0, 300);
            const response = await api.post('/ai/verify', {
                system_name: userQuestion,
                description,
            });
            setResult(response.data);
        } catch (error) {
            const detail = error?.response?.data?.detail;
            console.error('Verification failed:', error?.response?.data || error);
            alert(detail ? `Verification failed: ${detail}` : 'Verification failed: server error (500).');
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-12 animate-fade-in pb-20">
            <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center p-3 bg-blue-100 dark:bg-blue-900/30 rounded-2xl mb-4">
                    <ShieldCheck className="h-10 w-10 text-blue-600 dark:text-blue-400" />
                </div>
                <h1 className="text-4xl font-extrabold tracking-tight">
                    EU AI Act <span className="gradient-text">규제 위험 검증</span>
                </h1>
                <p className="text-lg text-slate-600 dark:text-slate-400">
                    시스템 목적과 고객 문서 텍스트를 기반으로 규제 위험과 조치 항목을 진단합니다.
                </p>
            </div>

            <div className="glass p-8 md:p-12 rounded-3xl space-y-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -z-10 transform translate-x-1/2 -translate-y-1/2"></div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">
                            사용자 질문 (권장)
                        </label>
                        <input
                            type="text"
                            className="w-full px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
                            placeholder="예: 이 문서를 EU AI Act 관점에서 검토하면 어떤 위험이 있나요?"
                            value={systemName}
                            onChange={(e) => setSystemName(e.target.value)}
                        />
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                            비우면 고객 문서 텍스트 앞부분이 자동으로 질문으로 사용됩니다.
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">
                            고객 문서 텍스트 (필수)
                        </label>
                        <textarea
                            rows="10"
                            className="w-full px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow resize-y"
                            placeholder="고객 문서 원문을 그대로 붙여넣으세요. (데이터 종류, 처리 방식, 배포 대상, 운영 정책 등)"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                        ></textarea>
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                            파일 업로드 대신 이 입력칸의 텍스트가 분석에 직접 사용됩니다.
                        </p>
                    </div>
                </div>

                <div className="pt-2 flex justify-end gap-4">
                    <button
                        onClick={handleVerify}
                        disabled={isAnalyzing}
                        className={`w-full md:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold flex justify-center items-center space-x-2 transition-all ${isAnalyzing ? 'opacity-75 cursor-not-allowed' : 'hover-glow'}`}
                    >
                        {isAnalyzing ? (
                            <>
                                <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full mr-2"></span>
                                분석 중...
                            </>
                        ) : (
                            <>
                                <span>규제 적합성 검증 시작</span>
                                <AlertTriangle className="w-5 h-5 ml-2 opacity-80" />
                            </>
                        )}
                    </button>
                </div>
            </div>

            {result && (
                <div className="glass p-8 md:p-12 rounded-3xl animate-fade-in relative overflow-hidden border-t-4 border-t-rose-500">
                    <div className="flex flex-col md:flex-row gap-8 items-start">
                        <div className="flex-shrink-0 text-center bg-rose-50 dark:bg-rose-900/20 p-6 rounded-2xl w-full md:w-auto">
                            <span className="block text-sm font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider mb-2">리스크 등급</span>
                            <span className="text-3xl font-black text-rose-600 dark:text-rose-400">{result.level}</span>
                            <div className="mt-4 pt-4 border-t border-rose-200 dark:border-rose-800/50">
                                <span className="block text-xs text-slate-500 mb-1">위험 지수</span>
                                <span className="text-2xl font-bold text-slate-800 dark:text-white">{result.score}<span className="text-sm font-normal text-slate-500">/100</span></span>
                            </div>
                        </div>

                        <div className="flex-grow space-y-6 w-full">
                            <div>
                                <h3 className="text-xl font-bold mb-2 flex items-center">
                                    <ShieldCheck className="w-6 h-6 mr-2 text-indigo-500" />
                                    AI 권고사항 및 해결 방안
                                </h3>
                                <p className="text-slate-600 dark:text-slate-400 text-sm">
                                    제출된 시스템 정보를 바탕으로 EU AI Act를 분석한 결과, 다음의 시정 조치가 필요합니다.
                                </p>
                            </div>

                            <ul className="space-y-4">
                                {(result.recommendations || []).map((rec, idx) => (
                                    <li key={idx} className="flex items-start bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
                                        <CheckCircle2 className="w-5 h-5 text-indigo-500 mt-0.5 mr-3 flex-shrink-0" />
                                        <span className="text-slate-800 dark:text-slate-200">{rec}</span>
                                    </li>
                                ))}
                            </ul>

                            {Array.isArray(result.key_findings) && result.key_findings.length > 0 && (
                                <div className="space-y-3">
                                    <h4 className="text-lg font-semibold text-slate-900 dark:text-white">핵심 설명</h4>
                                    <ul className="space-y-2">
                                        {result.key_findings.map((item, idx) => (
                                            <li key={`finding-${idx}`} className="text-sm text-slate-700 dark:text-slate-300 bg-white/70 dark:bg-slate-900/40 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                                                {item}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {Array.isArray(result.issues) && result.issues.length > 0 && (
                                <div className="space-y-3">
                                    <h4 className="text-lg font-semibold text-slate-900 dark:text-white">이슈 상세</h4>
                                    <div className="space-y-3">
                                        {result.issues.map((issue, idx) => (
                                            <div key={issue.issue_id || `issue-${idx}`} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/40 p-4 space-y-2">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                                                        {issue.issue_id || `ISSUE-${idx + 1}`}
                                                    </span>
                                                    <span className="text-xs px-2 py-1 rounded-full bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300">
                                                        {(issue.severity || 'unknown').toUpperCase()}
                                                    </span>
                                                    {issue.evidence_status && (
                                                        <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                                            {issue.evidence_status_label || issue.evidence_status}
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="font-semibold text-slate-900 dark:text-white">{issue.theme || '주제 없음'}</p>
                                                {Array.isArray(issue.related_article_briefs) && issue.related_article_briefs.length > 0 ? (
                                                    <div className="text-sm text-slate-600 dark:text-slate-300 space-y-1">
                                                        <p className="font-medium">관련 조항(요약)</p>
                                                        <ul className="list-disc list-inside space-y-1">
                                                            {issue.related_article_briefs.map((brief, briefIdx) => (
                                                                <li key={`brief-${idx}-${briefIdx}`}>{brief}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                ) : (
                                                    Array.isArray(issue.related_articles) && issue.related_articles.length > 0 && (
                                                        <p className="text-sm text-slate-600 dark:text-slate-300">
                                                            관련 조항: {issue.related_articles.join(', ')}
                                                        </p>
                                                    )
                                                )}
                                                {Array.isArray(issue.usecase_hints) && issue.usecase_hints.length > 0 && (
                                                    <p className="text-sm text-slate-600 dark:text-slate-300">
                                                        연관 사용사례: {issue.usecase_hints.join(', ')}
                                                    </p>
                                                )}
                                                {Array.isArray(issue.timeline_hints) && issue.timeline_hints.length > 0 && (
                                                    <p className="text-sm text-slate-600 dark:text-slate-300">
                                                        관련 시행시점: {issue.timeline_hints.join(', ')}
                                                    </p>
                                                )}
                                                {issue.finding && (
                                                    <p className="text-sm text-slate-700 dark:text-slate-200">
                                                        근거: {issue.finding}
                                                    </p>
                                                )}
                                                {issue.recommended_action && (
                                                    <p className="text-sm text-slate-700 dark:text-slate-200">
                                                        조치: {issue.recommended_action}
                                                    </p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Verify;
