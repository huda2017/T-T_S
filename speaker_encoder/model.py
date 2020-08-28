import torch
from torch import nn


class LSTMWithProjection(nn.Module):
    def __init__(self, input_size, hidden_size, proj_size):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.proj_size = proj_size
        self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.linear = nn.Linear(hidden_size, proj_size, bias=False)

    def forward(self, x):
        self.lstm.flatten_parameters()
        o, (_, _) = self.lstm(x)
        return self.linear(o)


class SpeakerEncoder(nn.Module):
    def __init__(self, input_dim, proj_dim=256, lstm_dim=768, num_lstm_layers=3):
        super().__init__()
        layers = []
        layers.append(LSTMWithProjection(input_dim, lstm_dim, proj_dim))
        for _ in range(num_lstm_layers - 1):
            layers.append(LSTMWithProjection(proj_dim, lstm_dim, proj_dim))
        self.layers = nn.Sequential(*layers)
        self._init_layers()

    def _init_layers(self):
        for name, param in self.layers.named_parameters():
            if "bias" in name:
                nn.init.constant_(param, 0.0)
            elif "weight" in name:
                nn.init.xavier_normal_(param)

    def forward(self, x):
        # TODO: implement state passing for lstms
        d = self.layers(x)
        d = torch.nn.functional.normalize(d[:, -1], p=2, dim=1)
        return d

    def inference(self, x):
        d = self.layers.forward(x)
        d = torch.nn.functional.normalize(d[:, -1], p=2, dim=1)
        return d

    def compute_embedding(self, x, num_frames=160, overlap=0.5):
        """
        Generate embeddings for a batch of utterances
        x: 1xTxD
        """
        num_overlap = int(num_frames * overlap)
        max_len = x.shape[1]
        embed = None
        cur_iter = 0
        for offset in range(0, max_len, num_frames - num_overlap):
            cur_iter += 1
            end_offset = min(x.shape[1], offset + num_frames)
            frames = x[:, offset:end_offset]
            if embed is None:
                embed = self.inference(frames)
            else:
                embed += self.inference(frames)
        return embed / cur_iter

    def batch_compute_embedding(self, x, seq_lens, num_frames=160, overlap=0.5):
        """
        Generate embeddings for a batch of utterances
        x: BxTxD
        """
        num_overlap = num_frames * overlap
        max_len = x.shape[1]
        embed = None
        num_iters = seq_lens / (num_frames - num_overlap)
        cur_iter = 0
        for offset in range(0, max_len, num_frames - num_overlap):
            cur_iter += 1
            end_offset = min(x.shape[1], offset + num_frames)
            frames = x[:, offset:end_offset]
            if embed is None:
                embed = self.inference(frames)
            else:
                embed[cur_iter <= num_iters, :] += self.inference(
                    frames[cur_iter <= num_iters, :, :]
                )
        return embed / num_iters

