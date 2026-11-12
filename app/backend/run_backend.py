from monitor.main import run

if __name__ == '__main__':
    import sys
    if '--browser-smoke' in sys.argv:
        from monitor.social_browser import smoke
        smoke()
    else:
        run()
