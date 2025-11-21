import torch
import torch.nn as nn

class CriterionNet(nn.Module):
    def __init__(self, criterion):
        super(CriterionNet, self).__init__()
        self.criterion = criterion

    def forward(self, outputs,targets):
        # outputs = self.model(*inputs)
        loss = self.criterion(outputs, targets)
        return loss.unsqueeze(0)

class LabelSmoothSoftmaxCEV1(nn.Module):
    '''
    This is the autograd version, you can also try the LabelSmoothSoftmaxCEV2 that uses derived gradients
    '''

    def __init__(self, label_smooth=0.1, reduction='mean', ignore_index=-100):
        super(LabelSmoothSoftmaxCEV1, self).__init__()
        self.label_smooth = label_smooth
        self.reduction = reduction
        self.lb_ignore = ignore_index
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, logits, label):
        '''
        args: logits: tensor of shape (N, C, H, W)
        args: label: tensor of shape(N, H, W)
        '''
        # overcome ignored label
        with torch.no_grad():
            num_classes = logits.size(1)
            label = label.clone().detach()
            ignore = label == self.lb_ignore
            n_valid = (ignore == 0).sum()
            label[ignore] = 0
            lb_pos, lb_neg = 1. - self.label_smooth, self.label_smooth / num_classes
            label = torch.empty_like(logits).fill_(
                lb_neg).scatter_(1, label.unsqueeze(1), lb_pos).detach()

        logs = self.log_softmax(logits)
        loss = -torch.sum(logs * label, dim=1)
        loss[ignore] = 0
        if self.reduction == 'mean':
            loss = loss.sum() / n_valid
        if self.reduction == 'sum':
            loss = loss.sum()

        return loss

class LSRCrossEntropyFunction(torch.autograd.Function):

    @staticmethod
    def forward(ctx, logits, label, label_smooth, reduction, lb_ignore):
        """
        logits: (B, C, L) or (B, C)
        label: (B, L) or (B,)
        """
        # 判断是否为3D输入
        is_3d = logits.dim() == 3
        
        if is_3d:
            # (B, C, L) -> (B*L, C)
            B, C, L = logits.size()
            logits = logits.transpose(1, 2).contiguous().view(-1, C)  # (B*L, C)
            label = label.view(-1)  # (B*L,)
        
        # prepare label
        num_classes = logits.size(1)
        label = label.clone().detach()
        
        # 裁剪标签到有效范围
        valid_mask = (label >= 0) & (label < num_classes)
        invalid_mask = ~valid_mask & (label != lb_ignore)
        
        # 将超出范围的标签设置为 ignore 标签
        if invalid_mask.any():
            label[invalid_mask] = lb_ignore
        
        ignore = label == lb_ignore
        n_valid = (ignore == 0).sum()
        
        if n_valid == 0:
            loss = torch.tensor(0., device=logits.device, requires_grad=True)
            ctx.mark_non_differentiable(loss)
            return loss
        
        label[ignore] = 0
        lb_pos, lb_neg = 1. - label_smooth, label_smooth / num_classes
        
        # 创建平滑标签
        label_smooth_tensor = torch.empty_like(logits).fill_(lb_neg)
        label_smooth_tensor.scatter_(1, label.unsqueeze(1), lb_pos)
        label_smooth_tensor[ignore] = 0  # 忽略的位置设为0
        
        coeff = (num_classes - 1) * lb_neg + lb_pos
        ctx.coeff = coeff
        ctx.ignore = ignore
        ctx.logits = logits
        ctx.label = label_smooth_tensor
        ctx.reduction = reduction
        ctx.n_valid = n_valid
        ctx.is_3d = is_3d
        if is_3d:
            ctx.shape = (B, C, L)

        # 计算损失
        log_probs = torch.log_softmax(logits, dim=1)
        loss = log_probs.neg_().mul_(label_smooth_tensor).sum(dim=1)
        
        if reduction == 'mean':
            loss = loss.sum().div_(n_valid)
        elif reduction == 'sum':
            loss = loss.sum()
        
        return loss

    @staticmethod
    def backward(ctx, grad_output):
        coeff = ctx.coeff
        ignore = ctx.ignore
        logits = ctx.logits
        label = ctx.label
        reduction = ctx.reduction
        n_valid = ctx.n_valid

        scores = torch.softmax(logits, dim=1).mul_(coeff)
        scores[ignore] = 0
        
        if reduction == 'none':
            grad = scores.sub_(label).mul_(grad_output.unsqueeze(1))
        elif reduction == 'sum':
            grad = scores.sub_(label).mul_(grad_output)
        elif reduction == 'mean':
            grad = scores.sub_(label).mul_(grad_output.div_(n_valid))
        
        # 如果输入是3D，恢复形状
        if ctx.is_3d:
            B, C, L = ctx.shape
            grad = grad.view(B, L, C).transpose(1, 2).contiguous()  # (B, C, L)
        
        return grad, None, None, None, None

class LSRCrossEntropyFunction1(torch.autograd.Function):

    @staticmethod
    def forward(ctx, logits, label, label_smooth, reduction, lb_ignore):
        # prepare label
        num_classes = logits.size(1)
        label = label.clone().detach()
        ignore = label == lb_ignore
        n_valid = (ignore == 0).sum()
        label[ignore] = 0
        lb_pos, lb_neg = 1. - label_smooth, label_smooth / num_classes
        label = torch.empty_like(logits).fill_(
            lb_neg).scatter_(1, label.unsqueeze(1), lb_pos).detach()

        ignore = ignore.nonzero()
        _, M = ignore.size()
        a, *b = ignore.chunk(M, dim=1)
        mask = [a, torch.arange(label.size(1)), *b]
        label[mask] = 0

        coeff = (num_classes - 1) * lb_neg + lb_pos
        ctx.coeff = coeff
        ctx.mask = mask
        ctx.logits = logits
        ctx.label = label
        ctx.reduction = reduction
        ctx.n_valid = n_valid

        loss = torch.log_softmax(logits, dim=1).neg_().mul_(label).sum(dim=1)
        if reduction == 'mean':
            loss = loss.sum().div_(n_valid)
        if reduction == 'sum':
            loss = loss.sum()
        return loss

    @staticmethod
    def backward(ctx, grad_output):
        coeff = ctx.coeff
        mask = ctx.mask
        logits = ctx.logits
        label = ctx.label
        reduction = ctx.reduction
        n_valid = ctx.n_valid

        scores = torch.softmax(logits, dim=1).mul_(coeff)
        scores[mask] = 0
        if reduction == 'none':
            grad = scores.sub_(label).mul_(grad_output.unsqueeze(1))
        elif reduction == 'sum':
            grad = scores.sub_(label).mul_(grad_output)
        elif reduction == 'mean':
            grad = scores.sub_(label).mul_(grad_output.div_(n_valid))
        return grad, None, None, None, None, None


class LabelSmoothSoftmaxCEV2(nn.Module):
    def __init__(self, label_smooth=0.1, reduction='mean', ignore_index=-100):
        super(LabelSmoothSoftmaxCEV2, self).__init__()
        self.label_smooth = label_smooth
        self.reduction = reduction
        self.lb_ignore = ignore_index

    def forward(self, logits, label):
        return LSRCrossEntropyFunction.apply(
            logits, label,
            self.label_smooth,
            self.reduction,
            self.lb_ignore)



class NMTCritierion(nn.Module):
    """
    TODO:
    1. Add label smoothing
    """

    def __init__(self, reduction='mean',ignore_index=0,label_smooth=0.0):
        super().__init__()
        self.label_smooth = label_smooth
        self.LogSoftmax = nn.LogSoftmax()

        if label_smooth > 0:
            self.criterion = nn.KLDivLoss(reduction=reduction)
        else:
            self.criterion = nn.NLLLoss(reduction=reduction, ignore_index=ignore_index)
        self.confidence = 1.0 - label_smooth

    def _label_smooth(self, num_tokens):
        # When label smoothing is turned on,
        # KL-divergence between q_{smoothed ground truth prob.}(w)
        # and p_{prob. computed by model}(w) is minimized.
        # If label smoothing value is set to zero, the loss
        # is equivalent to NLLLoss or CrossEntropyLoss.
        # All non-true labels are uniformly set to low-confidence.
        one_hot = torch.randn(1, num_tokens)
        one_hot.fill_(self.label_smooth / (num_tokens - 1))
        return one_hot

    def _bottle(self, v):
        return v.view(-1, v.size(2))

    def forward(self, dec_outs, labels):
        dec_outs.transpose(-2,-1)
        scores = self.LogSoftmax(dec_outs)
        num_tokens = scores.size(-1)

        # conduct label_smooth module
        gtruth = labels.view(-1)
        if self.confidence < 1:
            tdata = gtruth.detach()
            one_hot = self._label_smooth(num_tokens)  # Do label smoothing, shape is [M]
            if labels.is_cuda:
                one_hot = one_hot.cuda()
            tmp_ = one_hot.repeat(gtruth.size(0), 1)  # [N, M]
            tmp_.scatter_(1, tdata.unsqueeze(1), self.confidence)  # after tdata.unsqueeze(1) , tdata shape is [N,1]
            gtruth = tmp_.detach()
        loss = self.criterion(scores, gtruth)
        return loss