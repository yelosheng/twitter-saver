// ==UserScript==
// @name         Twitter Save Button
// @namespace    http://tampermonkey.net/
// @version      1.5
// @description  在Twitter/X帖子下添加保存按钮 (自定义图标 - 放在最后面，点击有旋转动画，图标外有圆圈)
// @author       You
// @match        https://twitter.com/*
// @match        https://x.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getResourceURL
// @resource     save_icon https://kxkl.tk:12580/resources/icon-128.png
// @connect      kxkl.tk
// ==/UserScript==

(function() {
    'use strict';

    // 1. 获取油猴预加载的本地图片资源地址
    const iconUrl = GM_getResourceURL("save_icon");

    // 2. 定义图标 HTML (现在包含一个外层圆圈 div)
    const saveIconContent = `
        <div class="save-icon-circle" style="
            display: flex;
            align-items: center;
            justify-content: center;
            width: 25px;       /* 圆圈的宽度 */
            height: 25px;      /* 圆圈的高度 */
            min-width: 25px;      /* 添加这行 */
            min-height: 25px;     /* 添加这行 */
            flex-shrink: 0;       /* 添加这行 */
            border-radius: 50%; /* 圆形 */
            border: 1px solid rgba(29, 155, 240, 0.4); /* 蓝色边框，半透明 */
            box-sizing: border-box; /* 边框包含在宽高内 */
            transition: border-color 0.2s ease-out; /* 边框颜色过渡 */
        ">
            <img src="${iconUrl}"
                 alt="Save"
                 class="save-icon-img"
                 style="
                    width: 17px;       /* 图片在圆圈内的大小 */
                    height: 17px;      /* 图片在圆圈内的大小 */
                    display: block;
                    pointer-events: none;
                    opacity: 0.7; /* 默认半透明 */
                 ">
        </div>
    `;

    // 3. 注入旋转动画的CSS样式
    function injectRotateCss() {
        if (!document.querySelector('#save-button-rotate-style')) {
            const style = document.createElement('style');
            style.id = 'save-button-rotate-style';
            style.textContent = `
                .save-icon-img.rotate-effect {
                    transform: rotate(360deg);
                    transition: transform 0.4s ease-out; /* 旋转动画效果 */
                }
            `;
            document.head.appendChild(style);
        }
    }

    // 创建保存按钮
    function createSaveButton(tweetElement) {
        const saveButton = document.createElement('div');

        saveButton.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 8px; border-radius: 50%; transition: all 0.2s; width: 35px; height: 35px; margin: 0 4px;"
                 class="save-button" title="保存推文">
                ${saveIconContent}
            </div>
        `;

        const buttonElement = saveButton.querySelector('.save-button');
        const iconImage = saveButton.querySelector('.save-icon-img');
        const iconCircle = saveButton.querySelector('.save-icon-circle'); // 获取外层圆圈元素

        // hover效果
        buttonElement.addEventListener('mouseenter', function() {
            this.style.backgroundColor = 'rgba(29, 155, 240, 0.1)';
            if(iconImage) iconImage.style.opacity = '1';
            if(iconCircle) iconCircle.style.borderColor = 'rgba(29, 155, 240, 0.8)'; // 悬停时边框颜色加深
        });

        buttonElement.addEventListener('mouseleave', function() {
            this.style.backgroundColor = 'transparent';
            if(iconImage) iconImage.style.opacity = '0.7';
            if(iconCircle) iconCircle.style.borderColor = 'rgba(29, 155, 240, 0.4)'; // 离开时边框颜色恢复
        });

        // 点击事件
        buttonElement.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            // 旋转动画逻辑
            if (iconImage) {
                iconImage.classList.remove('rotate-effect');
                void iconImage.offsetWidth;
                iconImage.classList.add('rotate-effect');
                setTimeout(() => {
                    iconImage.classList.remove('rotate-effect');
                }, 400);
            }

            // 点击缩放动画
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

    // 获取推文URL
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

    // Toast提示
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

    // 提交API
    function submitTweetToAPI(url) {
        showToast('正在保存推文...', 'info');
        if (typeof GM_xmlhttpRequest !== 'undefined') {
            GM_xmlhttpRequest({
                method: 'POST',
                url: 'https://kxkl.tk:12578/api/submit',
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify({ url: url }),
                onload: function(response) {
                    try {
                        const result = JSON.parse(response.responseText);
                        if (result.success) {
                            result.duplicate ? showToast(`推文已存在 (状态: ${result.status})`, 'warning') : showToast(`保存任务已提交 (ID: ${result.task_id})`, 'success');
                        } else {
                            showToast(`保存失败: ${result.message || result.error}`, 'error');
                        }
                    } catch (e) { showToast('响应解析失败', 'error'); }
                },
                onerror: () => showToast('网络请求失败', 'error'),
                ontimeout: () => showToast('请求超时', 'error'),
                timeout: 10000
            });
        } else {
            submitTweetToAPIFallback(url);
        }
    }

    async function submitTweetToAPIFallback(url) {
        try {
            const response = await fetch('https://cors-anywhere.herokuapp.com/https://kxkl.tk:12578/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify({ url: url })
            });
            const result = await response.json();
            if (result.success) {
                result.duplicate ? showToast(`推文已存在 (状态: ${result.status})`, 'warning') : showToast(`保存任务已提交 (ID: ${result.task_id})`, 'success');
            } else {
                showToast(`保存失败: ${result.message || result.error}`, 'error');
            }
        } catch (e) {
            showToast('保存失败，请复制URL手动提交', 'error');
        }
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
