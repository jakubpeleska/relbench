import pandas as pd
import torch_frame as pyf
import torch_geometric as pyg

from rtb.data.table import Table
from rtb.data.database import Database


def to_pyf_dataset(table: Table) -> pyf.data.Dataset:
    r"""Converts a Table to a PyF Dataset.

    Primary key and foreign keys are removed in this process."""

    raise NotImplementedError


def make_pkey_fkey_graph(db: Database) -> pyg.data.HeteroData:
    """
    Models the database as a heterogeneous graph.

    Instead of node embeddings in data.x, we store the tensor frames in data.tf.
    """

    data = pyg.data.HeteroData()

    for name, table in db.tables.items():
        # materialize the tables
        pyf_dataset = to_pyf_dataset(table)
        pyf_dataset.materialize()
        data[name].tf = pyf_dataset.tensor_frame

        # add time attribute
        data[name].time_stamp = torch.tensor(table.df[table.time_col])

        # add edges
        for col_name, pkey_name in table.fkeys.items():
            fkey_idx = torch.tensor(table.df[table.primary_key])
            pkey_idx = torch.tensor(table.df[col_name])

            # fkey -> pkey edges
            data[name, "f2p::" + col_name, pkey_name].edge_index = torch.stack(
                [fkey_idx, pkey_idx]
            )
            # pkey -> fkey edges
            data[pkey_name, "p2f::" + col_name, name].edge_index = torch.stack(
                [pkey_idx, fkey_idx]
            )

    return data


class AddTargetLabelTransform:
    r"""Adds the target label to the batch. The batch consists of disjoint
    subgraphs loaded via temporal sampling. The same input node can occur twice
    with different timestamps, and thus different subgraphs and labels. Hence
    labels cannot be stored in the Data object directly, and must be attached
    to the batch after the batch is created."""

    def __init__(self, labels: list[int | float]):
        self.labels = torch.tensor(labels)

    def __call__(self, batch: pyg.data.Batch) -> pyg.data.Batch:
        batch.y = self.labels[batch.input_id]
        return batch


def rolling_window_sampler(
    start_time: pd.Timestamp, end_time: pd.Timestamp, window_size: int, stride: int
) -> pd.DataFrame:
    """Returns a DataFrame with columns time_offset and time_cutoff."""
    
    df = pd.DataFrame()  
    start_time = int(start_time.timestamp())
    end_time = int(end_time.timestamp())

    df["time_offset"] = range(start_time, end_time - window_size, stride)
    df["time_cutoff"] = df["time_offset"] + window_size
    df["time_offset"] = df["time_offset"].astype("datetime64[s]")
    df["time_cutoff"] = df["time_cutoff"].astype("datetime64[s]")
    return df


def one_window_sampler(start_time: int, window_size: int) -> pd.DataFrame:
    """Returns a DataFrame with columns time_offset and time_cutoff."""

    df = pd.DataFrame()
    df["time_offset"] = [start_time]
    df["time_cutoff"] = [start_time + window_size]

    return df


def to_unix_time(column: pd.Series) -> pd.Series:
    """convert a timestamp column to unix time"""
    #return pd.to_datetime(column).astype('int64') // 10**9
    return pd.to_datetime(column).astype("datetime64[s]")