import { Link } from 'react-router-dom';
import { ShieldCheck, LogIn, Menu } from 'lucide-react';

function Header() {
    return (
        <header className="sticky top-0 z-50 glass w-full">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    {/* Logo Section */}
                    <div className="flex items-center space-x-2">
                        <Link to="/" className="flex items-center space-x-2 group">
                            <div className="p-2 bg-blue-600 rounded-lg group-hover:bg-blue-700 transition-colors">
                                <ShieldCheck className="h-6 w-6 text-white" />
                            </div>
                            <span className="font-bold text-xl tracking-tight text-slate-900 dark:text-white">
                                EU AI Act <span className="text-blue-600 dark:text-blue-400">Inspector</span>
                            </span>
                        </Link>
                    </div>

                    {/* Desktop Navigation */}
                    <nav className="hidden md:flex space-x-8">
                        <Link to="/" className="text-slate-600 hover:text-blue-600 dark:text-slate-300 dark:hover:text-blue-400 font-medium transition-colors">솔루션 안내</Link>
                        <Link to="/verify" className="text-slate-600 hover:text-blue-600 dark:text-slate-300 dark:hover:text-blue-400 font-medium transition-colors">위배 여부 검증</Link>
                    </nav>

                    {/* Action Buttons */}
                    <div className="hidden md:flex items-center space-x-4">
                        {localStorage.getItem('token') ? (
                            <button
                                onClick={() => {
                                    localStorage.removeItem('token');
                                    window.location.href = '/';
                                }}
                                className="flex items-center space-x-1 text-slate-600 hover:text-red-600 dark:text-slate-300 dark:hover:text-red-400 transition-colors font-medium"
                            >
                                로그아웃
                            </button>
                        ) : (
                            <>
                                <Link to="/login" className="flex items-center space-x-1 text-slate-600 hover:text-blue-600 dark:text-slate-300 dark:hover:text-blue-400 transition-colors">
                                    <LogIn className="h-5 w-5" />
                                    <span className="font-medium">로그인</span>
                                </Link>
                                <Link to="/register" className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-all hover-glow">
                                    무료 체험하기
                                </Link>
                            </>
                        )}
                    </div>

                    {/* Mobile Menu Button */}
                    <div className="md:hidden flex items-center">
                        <button className="text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white p-2">
                            <Menu className="h-6 w-6" />
                        </button>
                    </div>
                </div>
            </div>
        </header>
    );
}

export default Header;
