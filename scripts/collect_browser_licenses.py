"""Inclui os avisos do Playwright e do Node distribuído com seu driver."""
from pathlib import Path
import playwright

root = Path(__file__).resolve().parents[1]
package = Path(playwright.__file__).parent
sources = [root / 'app/desktop/src-tauri/windows/THIRD_PARTY_LICENSES.txt',
           package / 'driver/package/LICENSE', package / 'driver/package/NOTICE',
           package / 'driver/package/ThirdPartyNotices.txt', package / 'driver/LICENSE']
sections = [f'===== {path.name} ({"Tauri template" if index == 0 else "Playwright driver / Node.js"}) =====\n\n{path.read_text(encoding="utf-8")}'
            for index, path in enumerate(sources)]
target = root / 'dist/THIRD_PARTY_LICENSES.txt'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('\n\n'.join(sections), encoding='utf-8')
(root / 'dist/portable').mkdir(parents=True, exist_ok=True)
(root / 'dist/portable/THIRD_PARTY_LICENSES.txt').write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
print('Playwright and Node notices included in distribution.')
