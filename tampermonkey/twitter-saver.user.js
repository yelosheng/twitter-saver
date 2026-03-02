// ==UserScript==
// @name         Twitter/X Saver Save Button
// @namespace    https://github.com/yelosheng/twitter-saver
// @version      2.0
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

    function getSaveIconHtml() {
        const iconUrl = `${getBackendUrl()}/static/icon-128.png`;
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
            <img src="${iconUrl}"
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
