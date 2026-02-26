import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, Loader } from 'lucide-react';
import { register, login } from '../api/auth';

function Register() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    const handleRegister = async (e) => {
        e.preventDefault();
        setError(null);

        if (password !== confirmPassword) {
            setError('비밀번호가 일치하지 않습니다.');
            return;
        }

        if (password.length < 8) {
            setError('비밀번호는 최소 8자 이상이어야 합니다.');
            return;
        }

        setIsLoading(true);

        try {
            // 1. 회원가입 요청
            await register({ email, password });

            // 2. 가입 완료 후 자동 로그인 요청 (선택적)
            const loginData = await login(email, password);
            localStorage.setItem('token', loginData.access_token);

            // 홈페이지로 이동
            navigate('/');
        } catch (err) {
            if (err.response && err.response.data && err.response.data.detail) {
                setError(err.response.data.detail);
            } else {
                setError('회원가입에 실패했습니다. 다시 시도해주세요.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-slate-50 dark:bg-slate-900">
            {/* Background decoration */}
            <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/20 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-emerald-500/20 blur-[120px] pointer-events-none" />

            <div className="w-full max-w-md p-8 glass rounded-2xl shadow-xl z-10 border border-white/20 dark:border-slate-800">
                <div className="text-center mb-8">
                    <Link to="/" className="inline-flex items-center justify-center p-3 bg-blue-600 rounded-xl mb-4 hover:bg-blue-700 transition-colors shadow-lg shadow-blue-500/30">
                        <ShieldCheck className="h-8 w-8 text-white" />
                    </Link>
                    <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2 tracking-tight">
                        새로운 여정을 시작하세요
                    </h2>
                    <p className="text-slate-500 dark:text-slate-400">
                        무료로 가입하고 AI 컴플라이언스 솔루션을 사용해 보세요.
                    </p>
                </div>

                <form onSubmit={handleRegister} className="space-y-6">
                    {error && (
                        <div className="p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl text-red-600 dark:text-red-400 text-sm font-medium">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">이메일</label>
                            <input
                                type="email"
                                required
                                className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white"
                                placeholder="name@company.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">비밀번호</label>
                            <input
                                type="password"
                                required
                                className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white"
                                placeholder="최소 8자 이상"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">비밀번호 확인</label>
                            <input
                                type="password"
                                required
                                className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white"
                                placeholder="비밀번호 다시 입력"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-0.5 flex items-center justify-center space-x-2 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none"
                    >
                        {isLoading ? (
                            <Loader className="w-5 h-5 animate-spin" />
                        ) : (
                            <>
                                <span>무료로 가입하기</span>
                                <ArrowRight className="w-5 h-5" />
                            </>
                        )}
                    </button>
                </form>

                <div className="mt-8 text-center text-sm text-slate-600 dark:text-slate-400 font-medium">
                    이미 계정이 있으신가요?{' '}
                    <Link to="/login" className="text-blue-600 hover:text-blue-500 dark:text-blue-400 transition-colors">
                        로그인하기
                    </Link>
                </div>
            </div>
        </div>
    );
}

export default Register;
