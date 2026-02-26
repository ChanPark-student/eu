import { Cpu } from 'lucide-react';

function Footer() {
    return (
        <footer className="w-full bg-slate-900 text-slate-300 py-12 mt-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-4 gap-8">
                <div className="md:col-span-2 space-y-4">
                    <div className="flex items-center space-x-2">
                        <Cpu className="h-6 w-6 text-blue-500" />
                        <span className="font-bold text-xl tracking-tight text-white">
                            EU AI Act Inspector
                        </span>
                    </div>
                    <p className="text-slate-400 max-w-sm">
                        최신 EU 인공지능법 규제를 빠르고 정확하게 진단하여, 귀사의 성공적인 글로벌 AI 서비스 진출을 지원합니다.
                    </p>
                </div>

                <div>
                    <h3 className="text-white font-semibold mb-4">서비스</h3>
                    <ul className="space-y-2">
                        <li><a href="#" className="hover:text-blue-400 transition-colors">위배 여부 검증</a></li>
                        <li><a href="#" className="hover:text-blue-400 transition-colors">솔루션 첨삭</a></li>
                        <li><a href="#" className="hover:text-blue-400 transition-colors">기업 맞춤형 컨설팅</a></li>
                    </ul>
                </div>

                <div>
                    <h3 className="text-white font-semibold mb-4">고객 지원</h3>
                    <ul className="space-y-2">
                        <li><a href="#" className="hover:text-blue-400 transition-colors">자주 묻는 질문</a></li>
                        <li><a href="#" className="hover:text-blue-400 transition-colors">문의하기</a></li>
                        <li><a href="#" className="hover:text-blue-400 transition-colors">이용약관</a></li>
                    </ul>
                </div>
            </div>
            <div className="mt-12 pt-8 border-t border-slate-800 text-center text-slate-500 text-sm">
                <p>&copy; {new Date().getFullYear()} EU AI Act Inspector. All rights reserved.</p>
            </div>
        </footer>
    );
}

export default Footer;
