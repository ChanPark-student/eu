import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, Loader } from 'lucide-react';
import { login } from '../api/auth';

function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        try {
            const data = await login(email, password);
            // 저장
            localStorage.setItem('token', data.access_token);

            // 홈페이지로 이동
            navigate('/');
        } catch (err) {
            if (err.response && err.response.data && err.response.data.detail) {
                setError(err.response.data.detail);
            } else {
                setError('로그인에 실패했습니다. 다시 시도해주세요.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-slate-50 dark:bg-slate-900">
            {/* Background decoration */}
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/20 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-500/20 blur-[120px] pointer-events-none" />

            <div className="w-full max-w-md p-8 glass rounded-2xl shadow-xl z-10 border border-white/20 dark:border-slate-800">
                <div className="text-center mb-8">
                    <Link to="/" className="inline-flex items-center justify-center p-3 bg-blue-600 rounded-xl mb-4 hover:bg-blue-700 transition-colors shadow-lg shadow-blue-500/30">
                        <ShieldCheck className="h-8 w-8 text-white" />
                    </Link>
                    <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2 tracking-tight">
                        환영합니다 돌아오셨군요!
                    </h2>
                    <p className="text-slate-500 dark:text-slate-400">
                        계정에 로그인하시고 AI Compliance 검토를 시작하세요.
                    </p>
                </div>

                <form onSubmit={handleLogin} className="space-y-6">
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
                            <div className="flex justify-between mb-2">
                                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">비밀번호</label>
                                <a href="#" className="text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400">비밀번호 찾기</a>
                            </div>
                            <input
                                type="password"
                                required
                                className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
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
                                <span>로그인</span>
                                <ArrowRight className="w-5 h-5" />
                            </>
                        )}
                    </button>
                </form>

                <div className="mt-8 text-center text-sm text-slate-600 dark:text-slate-400 font-medium">
                    계정이 없으신가요?{' '}
                    <Link to="/register" className="text-blue-600 hover:text-blue-500 dark:text-blue-400 transition-colors">
                        무료 회원가입
                    </Link>
                </div>
            </div>
        </div>
    );
}

export default Login;
