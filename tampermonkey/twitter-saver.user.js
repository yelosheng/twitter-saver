// ==UserScript==
// @name         Twitter/X Saver Save Button
// @namespace    https://github.com/yelosheng/twitter-saver
// @version      2.2
// @description  在 Twitter/X 推文下添加保存按钮，一键归档到本地服务
// @author       yelosheng
// @match        https://twitter.com/*
// @match        https://x.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @connect      *
// ==/UserScript==

(function() {
    'use strict';

    const DEFAULT_BACKEND = 'http://localhost:6201';

    function getBackendUrl() {
        return GM_getValue('backendUrl', DEFAULT_BACKEND).replace(/\/$/, '');
    }

    GM_registerMenuCommand('⚙️ 设置后端地址', function() {
        const current = getBackendUrl();
        const newUrl = prompt('请输入后端服务地址（例：http://localhost:6201）', current);
        if (newUrl !== null && newUrl.trim()) {
            GM_setValue('backendUrl', newUrl.trim().replace(/\/$/, ''));
            alert('设置已保存，刷新页面生效');
        }
    });

    const ICON_DATA_URL = 'data:image/png;base64,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';

    function getSaveIconHtml() {
        return `
        <div class="save-icon-circle" style="
            display: flex;
            align-items: center;
            justify-content: center;
            width: 25px;
            height: 25px;
            min-width: 25px;
            min-height: 25px;
            flex-shrink: 0;
            border-radius: 50%;
            border: 1px solid rgba(29, 155, 240, 0.4);
            box-sizing: border-box;
            transition: border-color 0.2s ease-out;
        ">
            <img src="${ICON_DATA_URL}"
                 alt="Save"
                 class="save-icon-img"
                 style="
                    width: 17px;
                    height: 17px;
                    display: block;
                    pointer-events: none;
                    opacity: 0.7;
                 ">
        </div>
    `;
    }

    function injectRotateCss() {
        if (!document.querySelector('#save-button-rotate-style')) {
            const style = document.createElement('style');
            style.id = 'save-button-rotate-style';
            style.textContent = `
                .save-icon-img.rotate-effect {
                    transform: rotate(360deg);
                    transition: transform 0.4s ease-out;
                }
            `;
            document.head.appendChild(style);
        }
    }

    function createSaveButton(tweetElement) {
        const saveButton = document.createElement('div');
        saveButton.style.cssText = 'display: flex; align-items: center; align-self: center;';

        saveButton.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 8px; border-radius: 50%; transition: all 0.2s; width: 35px; height: 35px; margin: 0 4px;"
                 class="save-button" title="保存推文">
                ${getSaveIconHtml()}
            </div>
        `;

        const buttonElement = saveButton.querySelector('.save-button');
        const iconImage = saveButton.querySelector('.save-icon-img');
        const iconCircle = saveButton.querySelector('.save-icon-circle');

        buttonElement.addEventListener('mouseenter', function() {
            this.style.backgroundColor = 'rgba(29, 155, 240, 0.1)';
            if (iconImage) iconImage.style.opacity = '1';
            if (iconCircle) iconCircle.style.borderColor = 'rgba(29, 155, 240, 0.8)';
        });

        buttonElement.addEventListener('mouseleave', function() {
            this.style.backgroundColor = 'transparent';
            if (iconImage) iconImage.style.opacity = '0.7';
            if (iconCircle) iconCircle.style.borderColor = 'rgba(29, 155, 240, 0.4)';
        });

        buttonElement.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            if (iconImage) {
                iconImage.classList.remove('rotate-effect');
                void iconImage.offsetWidth;
                iconImage.classList.add('rotate-effect');
                setTimeout(() => {
                    iconImage.classList.remove('rotate-effect');
                }, 400);
            }

            this.style.transform = 'scale(0.8)';
            setTimeout(() => {
                this.style.transform = 'scale(1)';
            }, 150);

            const tweetUrl = getTweetUrl(tweetElement);

            if (tweetUrl) {
                submitTweetToAPI(tweetUrl);
            } else {
                showToast('无法获取推文URL', 'error');
            }
        });

        return saveButton;
    }

    function getTweetUrl(tweetElement) {
        try {
            const timeElement = tweetElement.querySelector('time');
            if (timeElement && timeElement.parentElement && timeElement.parentElement.href) {
                return timeElement.parentElement.href;
            }
            const statusLinks = tweetElement.querySelectorAll('a[href*="/status/"]');
            if (statusLinks.length > 0) {
                return statusLinks[0].href;
            }
            const article = tweetElement.closest('article');
            if (article) {
                const links = article.querySelectorAll('a[href*="/status/"]');
                if (links.length > 0) {
                    return links[0].href;
                }
            }
            const currentUrl = window.location.href;
            if (currentUrl.includes('/status/')) {
                return currentUrl.split('?')[0];
            }
            return null;
        } catch (error) {
            console.error('获取推文URL时出错:', error);
            return null;
        }
    }

    function showToast(message, type = 'info') {
        const existingToast = document.querySelector('.save-toast');
        if (existingToast) existingToast.remove();

        const toast = document.createElement('div');
        toast.className = 'save-toast';
        const bgColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : type === 'warning' ? '#ff9800' : '#2196F3';

        toast.style.cssText = `
            position: fixed; top: 20px; right: 20px; background: ${bgColor}; color: white;
            padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3); z-index: 10000; max-width: 300px;
            animation: slideIn 0.3s ease-out; display: flex; align-items: center;
        `;

        if (!document.querySelector('#toast-style')) {
            const style = document.createElement('style');
            style.id = 'toast-style';
            style.textContent = `@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } } @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }`;
            document.head.appendChild(style);
        }

        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function submitTweetToAPI(url) {
        const apiUrl = `${getBackendUrl()}/api/submit`;
        showToast('正在保存推文...', 'info');
        GM_xmlhttpRequest({
            method: 'POST',
            url: apiUrl,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify({ url }),
            onload: function(response) {
                try {
                    const result = JSON.parse(response.responseText);
                    if (result.success) {
                        result.duplicate
                            ? showToast(`推文已存在 (状态: ${result.status})`, 'warning')
                            : showToast(`保存任务已提交 (ID: ${result.task_id})`, 'success');
                    } else {
                        showToast(`保存失败: ${result.message || result.error}`, 'error');
                    }
                } catch (e) {
                    showToast('响应解析失败', 'error');
                }
            },
            onerror: () => showToast('网络请求失败，请检查后端地址设置', 'error'),
            ontimeout: () => showToast('请求超时', 'error'),
            timeout: 10000
        });
    }

    function addSaveButtonToTweet(tweetElement) {
        if (tweetElement.querySelector('.save-button')) return;

        let actionBar = tweetElement.querySelector('div[role="group"]');

        if (!actionBar) {
            actionBar = tweetElement.querySelector('div:has(> div:nth-child(3))');
            if (!actionBar) {
                const buttonContainers = tweetElement.querySelectorAll('div');
                for (let container of buttonContainers) {
                    if (container.children.length >= 4) {
                        actionBar = container;
                        break;
                    }
                }
            }
        }

        if (actionBar) {
            const saveButton = createSaveButton(tweetElement);
            actionBar.appendChild(saveButton);
        }
    }

    function observeTweets() {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        const tweets = node.querySelectorAll('article[data-testid="tweet"]');
                        tweets.forEach(addSaveButtonToTweet);
                        if (node.matches && node.matches('article[data-testid="tweet"]')) {
                            addSaveButtonToTweet(node);
                        }
                    }
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    function init() {
        injectRotateCss();

        const start = () => {
            const existingTweets = document.querySelectorAll('article[data-testid="tweet"]');
            existingTweets.forEach(addSaveButtonToTweet);
            observeTweets();
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => setTimeout(start, 1000));
        } else {
            setTimeout(start, 1000);
        }
    }

    init();

})();
