import { useState } from 'react';
import { Upload, ShieldCheck, AlertTriangle, FileText, CheckCircle2 } from 'lucide-react';

function Verify() {
    const [file, setFile] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const [systemName, setSystemName] = useState('');
    const [description, setDescription] = useState('');

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const handleVerify = () => {
        if (!systemName || !description) {
            alert("시스템 이름과 설명을 입력해주세요.");
            return;
        }

        setIsAnalyzing(true);
        // Simulate API call to backend AI endpoint
        setTimeout(() => {
            setIsAnalyzing(false);
            setResult({
                level: 'High Risk', // Simulate High Risk
                score: 82,
                recommendations: [
                    "인간의 감독(Human Oversight) 메커니즘을 명시적으로 문서화하십시오.",
                    "데이터 편향성(Data Bias) 검증 리포트를 추가로 제출해야 합니다.",
                    "사용자에게 AI와 상호작용하고 있음을 명확히 고지하십시오."
                ]
            });
        }, 3000);
    };

    return (
        <div className="max-w-4xl mx-auto space-y-12 animate-fade-in pb-20">
            {/* Header */}
            <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center p-3 bg-blue-100 dark:bg-blue-900/30 rounded-2xl mb-4">
                    <ShieldCheck className="h-10 w-10 text-blue-600 dark:text-blue-400" />
                </div>
                <h1 className="text-4xl font-extrabold tracking-tight">EU AI Act <span className="gradient-text">위배 여부 검증</span></h1>
                <p className="text-lg text-slate-600 dark:text-slate-400">
                    AI 시스템의 세부 정보와 산출물을 제출하여 글로벌 규제 기준에 부합하는지 즉각 확인하세요.
                </p>
            </div>

            {/* Input Form */}
            <div className="glass p-8 md:p-12 rounded-3xl space-y-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -z-10 transform translate-x-1/2 -translate-y-1/2"></div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">AI 시스템 명칭</label>
                        <input
                            type="text"
                            className="w-full px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
                            placeholder="예: 안면 인식 기반 출입 통제 시스템"
                            value={systemName}
                            onChange={(e) => setSystemName(e.target.value)}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">시스템 목적 및 설명</label>
                        <textarea
                            rows="4"
                            className="w-full px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow resize-none"
                            placeholder="시스템의 주요 기능, 사용되는 데이터의 종류, 대상 사용자 등을 상세히 기입해주세요."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                        ></textarea>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">관련 문서 업로드 (기술 명세서, 데이터 정책 등)</label>
                        <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-slate-300 dark:border-slate-600 border-dashed rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer relative">
                            <input
                                type="file"
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                onChange={handleFileChange}
                                accept=".pdf,.doc,.docx"
                            />
                            <div className="space-y-1 text-center">
                                <Upload className="mx-auto h-12 w-12 text-slate-400" />
                                <div className="text-sm text-slate-600 dark:text-slate-400">
                                    <span className="font-medium text-blue-600 dark:text-blue-400">파일 찾기</span> 또는 드래그 앤 드롭
                                </div>
                                <p className="text-xs text-slate-500 flex justify-center gap-1 items-center">
                                    <FileText className="w-3 h-3" /> {file ? <span className="text-blue-600 font-semibold">{file.name}</span> : "PDF, DOCX 최대 10MB"}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="pt-4 flex justify-end gap-4">
                    <button
                        onClick={handleVerify}
                        disabled={isAnalyzing}
                        className={`w-full md:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold flex justify-center items-center space-x-2 transition-all ${isAnalyzing ? 'opacity-75 cursor-not-allowed' : 'hover-glow'}`}
                    >
                        {isAnalyzing ? (
                            <>
                                <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full mr-2"></span>
                                AI 분석 중...
                            </>
                        ) : (
                            <>
                                <span>규제 위배 검증 시작</span>
                                <AlertTriangle className="w-5 h-5 ml-2 opacity-80" />
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Verification Result */}
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
                                {result.recommendations.map((rec, idx) => (
                                    <li key={idx} className="flex items-start bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
                                        <CheckCircle2 className="w-5 h-5 text-indigo-500 mt-0.5 mr-3 flex-shrink-0" />
                                        <span className="text-slate-800 dark:text-slate-200">{rec}</span>
                                    </li>
                                ))}
                            </ul>

                            <div className="pt-4 flex justify-end">
                                <button className="text-blue-600 dark:text-blue-400 font-medium hover:underline flex items-center text-sm">
                                    상세 리포트 다운로드 (PDF)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Verify;
